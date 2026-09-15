import os
from urllib.parse import urlparse

import httpx
import streamlit as st


API_ANALYSIS_URL = os.getenv(
    "API_ANALYSIS_URL",
    "http://traefik/api/analisis",
)

CATEGORY_LABELS = {
    "privacy_and_data_processing": "Privacidad y tratamiento de datos",
    "data_transfer_to_third_parties": "Transferencia de datos a terceros",
    "unilateral_modification": "Modificación unilateral",
    "unilateral_termination": "Terminación unilateral",
    "limitation_of_liability": "Limitación de responsabilidad",
    "dispute_resolution": "Resolución de controversias",
    "consumer_rights_restriction": "Restricción de derechos del consumidor",
    "user_content_and_intellectual_property": (
        "Contenido del usuario y propiedad intelectual"
    ),
    "other_contractual_risk": "Otro riesgo contractual",
}

CLASSIFICATION_LABELS = {
    "not_potentially_abusive": "No potencialmente abusiva",
    "potentially_abusive": "Potencialmente abusiva",
    "high_risk_abusiveness": "Alto riesgo de abusividad",
}

RISK_LABELS = {
    "low": "Bajo",
    "medium": "Medio",
    "high": "Alto",
}

EVIDENCE_LABELS = {
    "sufficient": "Suficiente",
    "partial": "Parcial",
    "insufficient": "Insuficiente",
}


def is_valid_url(value: str) -> bool:
    """Comprueba que la entrada sea una URL HTTP o HTTPS válida."""
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def render_legal_basis(
    legal_basis: list[dict[str, object]],
) -> None:
    """Muestra las fuentes jurídicas usadas por el analizador."""

    if not legal_basis:
        st.write("No se seleccionaron fundamentos jurídicos.")
        return

    for index, evidence in enumerate(
        legal_basis,
        start=1,
    ):
        title = evidence.get("title") or "Fuente jurídica"

        with st.expander(
            f"Fundamento jurídico {index}: {title}"
        ):
            citation = evidence.get("official_citation")
            issuing_body = evidence.get("issuing_body")
            jurisdiction = evidence.get("jurisdiction")
            document_type = evidence.get("document_type")
            binding_level = evidence.get("binding_level")
            status = evidence.get("status")
            content = evidence.get("content")
            source_url = evidence.get("source_url")

            if citation:
                st.write(
                    f"**Citación oficial:** {citation}"
                )

            if issuing_body:
                st.write(
                    f"**Organismo emisor:** {issuing_body}"
                )

            if jurisdiction:
                st.write(
                    f"**Jurisdicción:** {jurisdiction}"
                )

            if document_type:
                st.write(
                    f"**Tipo de documento:** {document_type}"
                )

            if binding_level:
                st.write(
                    f"**Nivel vinculante:** {binding_level}"
                )

            if status:
                st.write(
                    f"**Estado:** {status}"
                )

            if content:
                st.markdown("**Contenido recuperado:**")
                st.write(content)

            if source_url:
                st.markdown(
                    f"[Consultar fuente]({source_url})"
                )


def render_clause(
    item: dict[str, object],
) -> None:
    """Muestra un resultado individual del analizador legal."""

    clause_order = item.get("clause_order", "-")
    response_status = item.get("status")

    if response_status != "success":
        with st.expander(
            f"Cláusula {clause_order} — Error de análisis"
        ):
            st.error(
                item.get("error")
                or "No fue posible analizar esta cláusula."
            )
        return

    assessment = item.get("result")

    if not isinstance(assessment, dict):
        return

    category = assessment.get("category")
    classification = assessment.get("classification")
    risk_level = assessment.get("risk_level")
    analysis_status = assessment.get("analysis_status")

    category_label = CATEGORY_LABELS.get(
        str(category),
        str(category),
    )

    if analysis_status == "requires_review":
        status_label = "Requiere revisión"
        status_class = "risk-review"
    else:
        status_label = RISK_LABELS.get(
            str(risk_level),
            str(risk_level),
        )
        status_class = f"risk-{risk_level}"

    with st.expander(
        f"Cláusula {clause_order} — {category_label}"
    ):
        st.markdown(
            (
                f'<span class="risk-badge {status_class}">'
                f"{status_label}"
                "</span>"
            ),
            unsafe_allow_html=True,
        )

        st.markdown("#### Fragmento analizado")
        st.write(
            assessment.get("relevant_fragment")
            or "No disponible."
        )

        st.markdown("#### Clasificación")

        if classification is None:
            st.write("Sin clasificación")
        else:
            st.write(
                CLASSIFICATION_LABELS.get(
                    str(classification),
                    str(classification),
                )
            )

        if risk_level is not None:
            st.write(
                "**Nivel de riesgo:** "
                + RISK_LABELS.get(
                    str(risk_level),
                    str(risk_level),
                )
            )

        st.markdown("#### Justificación")
        st.write(
            assessment.get("justification")
            or "No disponible."
        )

        st.markdown("#### Recomendación")
        st.write(
            assessment.get("recommendation")
            or "No disponible."
        )

        evidence = assessment.get(
            "evidence_sufficiency"
        )

        st.write(
            "**Suficiencia de evidencia jurídica:** "
            + EVIDENCE_LABELS.get(
                str(evidence),
                str(evidence),
            )
        )

        requires_review = assessment.get(
            "requires_human_review"
        )

        if requires_review:
            st.write(
                "**Revisión humana requerida:** Sí"
            )
        else:
            st.write(
                "**Revisión humana requerida:** No"
            )

        st.markdown("#### Fundamento jurídico")

        legal_basis = assessment.get(
            "legal_basis",
            [],
        )

        if isinstance(legal_basis, list):
            render_legal_basis(
                [
                    item
                    for item in legal_basis
                    if isinstance(item, dict)
                ]
            )


def render_analysis_results(
    data: dict[str, object],
) -> None:
    """Muestra el resumen y los resultados recibidos."""

    st.divider()
    st.subheader("Resultados del análisis")

    platform = data.get("platform")
    source_url = data.get("source_url")

    if platform:
        st.write(
            f"**Plataforma:** {platform}"
        )

    if source_url:
        st.write(
            f"**URL analizada:** {source_url}"
        )

    columns = st.columns(4)

    columns[0].metric(
        "Cláusulas",
        data.get("total_clauses", 0),
    )

    columns[1].metric(
        "Analizadas",
        data.get("analyzed_clauses", 0),
    )

    columns[2].metric(
        "Exitosas",
        data.get("successful_clauses", 0),
    )

    columns[3].metric(
        "Fallidas",
        data.get("failed_clauses", 0),
    )

    results = data.get("results", [])

    if not isinstance(results, list):
        return

    st.markdown("### Cláusulas analizadas")

    if not results:
        st.info(
            "No se obtuvieron cláusulas para mostrar."
        )
        return

    for item in results:
        if isinstance(item, dict):
            render_clause(item)


st.set_page_config(
    page_title="Análisis de Términos de Servicio",
    layout="wide",
)

st.markdown(
    """
    <style>
        .stApp {
            background-color: #f7f7f8;
        }

        .block-container {
            max-width: 1180px;
            padding-top: 2.5rem;
            padding-bottom: 4rem;
        }

        h1 {
            color: #8f1d2c;
            font-weight: 650;
        }

        h2, h3, h4 {
            color: #252525;
        }

        div[data-testid="stForm"] {
            background-color: #ffffff;
            border: 1px solid #dedede;
            border-top: 4px solid #8f1d2c;
            border-radius: 8px;
            padding: 1.25rem;
        }

        div[data-testid="stFormSubmitButton"] button {
            background-color: #8f1d2c;
            color: #ffffff;
            border-color: #8f1d2c;
            border-radius: 6px;
            font-weight: 600;
        }

        div[data-testid="stFormSubmitButton"] button:hover {
            background-color: #741724;
            color: #ffffff;
            border-color: #741724;
        }

        div[data-testid="stMetric"] {
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 7px;
            padding: 1rem;
        }

        div[data-testid="stExpander"] {
            background-color: #ffffff;
            border: 1px solid #dddddd;
            border-radius: 7px;
            margin-bottom: 0.55rem;
        }

        .risk-badge {
            display: inline-block;
            padding: 0.3rem 0.7rem;
            border-radius: 5px;
            font-weight: 600;
            margin-bottom: 0.8rem;
        }

        .risk-low {
            background-color: #e8f2ec;
            color: #285b3a;
            border: 1px solid #bdd8c5;
        }

        .risk-medium {
            background-color: #fff3d8;
            color: #775515;
            border: 1px solid #ead295;
        }

        .risk-high {
            background-color: #f7e3e6;
            color: #8f1d2c;
            border: 1px solid #ddb8be;
        }

        .risk-review {
            background-color: #eeeeee;
            color: #4d4d4d;
            border: 1px solid #d1d1d1;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Análisis de Términos de Servicio")

st.write(
    "Sistema multiagente para detectar cláusulas "
    "potencialmente abusivas en plataformas SaaS."
)

with st.form("analysis_form"):
    url = st.text_input(
        "URL de los Términos de Servicio",
        placeholder="https://ejemplo.com/terms",
    )

    submitted = st.form_submit_button(
        "Analizar términos"
    )


if submitted:
    normalized_url = url.strip()

    if not is_valid_url(normalized_url):
        st.error(
            "Ingrese una URL válida que utilice HTTP o HTTPS."
        )
    else:
        with st.status(
            "Procesando los Términos de Servicio...",
            expanded=True,
        ) as processing_status:
            status_message = st.empty()

            status_message.write(
                "El sistema está ejecutando el flujo multiagente. "
                "Este proceso puede tardar algunos minutos."
            )

            try:
                response = httpx.post(
                    API_ANALYSIS_URL,
                    json={
                        "url": normalized_url,
                    },
                    timeout=httpx.Timeout(
                        None,
                        connect=10.0,
                    ),
                )

                response.raise_for_status()

                analysis_result = response.json()
                st.session_state.analysis_result = analysis_result

                pipeline_status = analysis_result.get("status")

                if pipeline_status == "success":
                    status_message.write(
                        "El procesamiento multiagente "
                        "finalizó correctamente."
                    )
                    processing_status.update(
                        label="Análisis completado",
                        state="complete",
                        expanded=False,
                    )

                elif pipeline_status == "partial":
                    status_message.write(
                        "El procesamiento finalizó con "
                        "resultados parciales."
                    )
                    processing_status.update(
                        label="Análisis completado parcialmente",
                        state="complete",
                        expanded=False,
                    )

                elif pipeline_status == "error":
                    status_message.write(
                        "El procesamiento no pudo "
                        "completarse correctamente."
                    )
                    processing_status.update(
                        label="El análisis no pudo completarse",
                        state="error",
                        expanded=True,
                    )

                else:
                    status_message.write(
                        "El backend devolvió un estado "
                        "final no esperado."
                    )
                    processing_status.update(
                        label="Estado del análisis no reconocido",
                        state="error",
                        expanded=True,
                    )

            except httpx.HTTPStatusError as error:
                status_message.write(
                    "El procesamiento multiagente "
                    "se interrumpió."
                )

                processing_status.update(
                    label="El análisis no pudo completarse",
                    state="error",
                    expanded=True,
                )

                st.error(
                    "El backend rechazó la solicitud. "
                    f"Código HTTP: "
                    f"{error.response.status_code}"
                )

            except httpx.RequestError:
                status_message.write(
                    "No fue posible completar "
                    "el procesamiento."
                )

                processing_status.update(
                    label=(
                        "No fue posible completar "
                        "el análisis"
                    ),
                    state="error",
                    expanded=True,
                )

                st.error(
                    "No fue posible establecer comunicación "
                    "con el servicio de análisis."
                )


analysis_result = st.session_state.get(
    "analysis_result"
)

if isinstance(
    analysis_result,
    dict,
):
    render_analysis_results(
        analysis_result
    )
