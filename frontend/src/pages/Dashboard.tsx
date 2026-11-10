import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Asset, Header } from "../components/Design";
import { useAuth } from "../features/auth-context";
import { useGuestAccessLink } from "../features/guest-access";
import { getInterviews, type InterviewSummary } from "../services/interviews";
import { getVacancies, type VacancySummary } from "../services/vacancies";

type Recent<T> = { ownerId: number; items: T[]; error: string };

export function Dashboard() {
  const { candidate } = useAuth();
  const onInterviewClick = useGuestAccessLink("interviews");
  const [vacancies, setVacancies] = useState<Recent<VacancySummary> | null>(null);
  const [interviews, setInterviews] = useState<Recent<InterviewSummary> | null>(null);
  const accountId = candidate?.password_expired ? undefined : candidate?.id;
  useEffect(() => {
    if (accountId === undefined) return;
    let active = true;
    getVacancies()
      .then((items) => {
        if (active) setVacancies({ ownerId: accountId, items: items.slice(0, 3), error: "" });
      })
      .catch(() => {
        if (active) setVacancies({ ownerId: accountId, items: [], error: "No se pudieron cargar las vacantes recientes." });
      });
    getInterviews()
      .then((items) => {
        if (active) setInterviews({ ownerId: accountId, items: items.slice(0, 3), error: "" });
      })
      .catch(() => {
        if (active) setInterviews({ ownerId: accountId, items: [], error: "No se pudieron cargar las entrevistas recientes." });
      });
    return () => {
      active = false;
    };
  }, [accountId]);
  const recentVacancies = vacancies?.ownerId === accountId ? vacancies : null;
  const recentInterviews = interviews?.ownerId === accountId ? interviews : null;
  const cards = [
    {
      title: "Analizar vacante",
      description:
        "Pegá la descripción de un puesto para identificar requisitos y posibles alertas de la oferta.",
      action: "Comenzar análisis",
      icon: "imgSearch",
      to: "/vacantes/nueva",
    },
    {
      title: "Comparar curriculum-vacante",
      description:
        "Obtén feedback impulsado por IA para mejorar tus habilidades acorde con una vacante de interés",
      action: "Comenzar comparación",
      icon: "imgFile1",
      to: "/comparaciones",
    },
    {
      title: "Practicar entrevista",
      description:
        "Entrena con un simulador interactivo adaptado a tu perfil y la vacante a la que aplicas",
      action: "Iniciar simulación",
      icon: "imgMic",
      to: "/entrevistas",
    },
  ];
  return (
    <>
      <Header
        title={`Bienvenido${candidate ? `, ${candidate.nickname || candidate.first_name}` : ""}`}
        screen="dashboard"
      />

      <div className="action-cards">
        {cards.map((card, i) => (
          <article className="action-card" key={card.title}>
            <div
              className={i === 0 ? "icon-badge primary-badge" : "icon-badge"}
            >
              <Asset screen="dashboard" name={card.icon} />
            </div>
            <h2>{card.title}</h2>
            <p>{card.description}</p>
            <Link
              className="card-action"
              to={card.to}
              onClick={
                card.to === "/entrevistas" ? onInterviewClick : undefined
              }
            >
              {card.action}
              <Asset screen="dashboard" name="imgChevronRight" />
            </Link>
          </article>
        ))}
      </div>
      <div className="dashboard-split">
        <section>
          <h2 className="section-title">Vacantes analizadas recientemente</h2>
          <div className="jobs-list">
            {recentVacancies?.items.map((vacancy) => (
              <Link
                className="job-row"
                key={vacancy.id}
                to={`/vacantes/${vacancy.id}/analisis`}
              >
                <div>
                  <h3>{vacancy.title}</h3>
                  <p>{vacancy.company || "Empresa no indicada"}</p>
                </div>
                <div className="job-match">
                  <span className="pill cyan">
                    {vacancy.risk_percentage ?? 0}% Riesgo orientativo
                  </span>
                  <span className="muted">
                    {new Date(vacancy.created_at).toLocaleDateString("es-AR")}
                  </span>
                </div>
              </Link>
            ))}
            {accountId !== undefined && !recentVacancies ? <p role="status">Cargando vacantes recientes…</p> : recentVacancies?.error ? <p className="field-error" role="alert">{recentVacancies.error}</p> : !recentVacancies?.items.length && (
              <div className="empty-state">
                <span className="empty-state-symbol" aria-hidden="true">
                  ↗
                </span>
                <h3>Todavía no hay vacantes analizadas</h3>
                <p>
                  Cuando analices una oferta, aparecerá en este espacio para que
                  puedas retomarla.
                </p>
                <Link className="card-action" to="/vacantes/nueva">
                  Analizar una vacante <span aria-hidden="true">→</span>
                </Link>
              </div>
            )}
          </div>
        </section>
        <section className="interviews-card">
          <h2>Entrevistas recientes</h2>
          <p>Revisá tus resultados y seguí practicando a tu ritmo.</p>
          {accountId !== undefined && !recentInterviews ? <p role="status">Cargando entrevistas recientes…</p> : recentInterviews?.error ? <p className="field-error" role="alert">{recentInterviews.error}</p> : recentInterviews?.items.length ? (
            <>
              <div className="interviews-list">
                {recentInterviews.items.map((interview) => (
                  <Link className="interview-row" key={interview.id} to={`/entrevistas/${interview.id}`}>
                    <div>
                      <h3>{interview.vacancy_title}</h3>
                      <span className="pill green">{interview.score}/100</span>
                    </div>
                    <div>
                      <span className="muted">{new Date(interview.created_at).toLocaleDateString("es-AR")}</span>
                      <span>Ver resultado →</span>
                    </div>
                  </Link>
                ))}
              </div>
              <Link className="card-action" to="/entrevistas">Ver todas las entrevistas →</Link>
            </>
          ) : (
            <div className="empty-state interview-empty">
              <span className="empty-state-symbol" aria-hidden="true">◎</span>
              <h3>Tu práctica empieza acá</h3>
              <p>Respondé preguntas técnicas basadas en una vacante y consultá tus resultados cuando termines.</p>
              <Link className="card-action" to="/entrevistas" onClick={onInterviewClick}>
                Practicar ahora <span aria-hidden="true">→</span>
              </Link>
            </div>
          )}
        </section>
      </div>
    </>
  );
}
