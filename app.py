"""RaveForge App — Streamlit workbench for Medidata Rave ODM submissions."""
from __future__ import annotations

import streamlit as st

from raveforge import (
    ActionType,
    DiagnosticReport,
    QueryRecipient,
    QueryStatus,
    RaveDiagnostics,
    RaveTransaction,
    RWSError,
    ValidationError,
    validate,
)
from raveforge.rws_client import RWSClient

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RaveForge",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "client" not in st.session_state:
    st.session_state.client = None
if "tx" not in st.session_state:
    st.session_state.tx = None
if "validation_issues" not in st.session_state:
    st.session_state.validation_issues = []
if "last_report" not in st.session_state:
    st.session_state.last_report = None
if "subjects" not in st.session_state:
    st.session_state.subjects: list[dict] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _action_options() -> dict[str, ActionType | None]:
    return {
        "(none)": None,
        "Upsert": ActionType.UPSERT,
        "Insert": ActionType.INSERT,
        "Update": ActionType.UPDATE,
        "Remove": ActionType.REMOVE,
    }


def _query_status_options() -> dict[str, QueryStatus | None]:
    return {
        "(none)": None,
        "Open": QueryStatus.OPEN,
        "Answered": QueryStatus.ANSWERED,
        "Closed": QueryStatus.CLOSED,
        "Cancelled": QueryStatus.CANCELLED,
    }


def _query_recipient_options() -> dict[str, QueryRecipient | None]:
    return {
        "(none)": None,
        "Site": QueryRecipient.SITE,
        "Site from DM": QueryRecipient.SITE_FROM_DM,
        "Site from System": QueryRecipient.SITE_FROM_SYSTEM,
        "DM from Site": QueryRecipient.DM_FROM_SITE,
        "DM from Sponsor": QueryRecipient.DM_FROM_SPONSOR,
        "Sponsor from Site": QueryRecipient.SPONSOR_FROM_SITE,
    }


def _build_transaction(study_oid: str, subjects: list[dict]) -> RaveTransaction:
    """Assemble a RaveTransaction from the session subjects list."""
    tx = RaveTransaction(study_oid)
    actions = _action_options()
    statuses = _query_status_options()
    recipients = _query_recipient_options()

    for subj in subjects:
        tx.subject(
            subj["key"],
            subj["site_oid"],
            action=actions.get(subj.get("action", "(none)")),
        )
        for event in subj.get("events", []):
            tx.event(
                event["oid"],
                repeat_key=event.get("repeat_key") or None,
                action=actions.get(event.get("action", "(none)")),
            )
            for form in event.get("forms", []):
                tx.form(
                    form["oid"],
                    repeat_key=form.get("repeat_key") or None,
                    action=actions.get(form.get("action", "(none)")),
                )
                for group in form.get("item_groups", []):
                    tx.item_group(
                        group["oid"],
                        repeat_key=group.get("repeat_key") or None,
                        specified_items_only=group.get(
                            "specified_items_only", False
                        ),
                        action=actions.get(group.get("action", "(none)")),
                    )
                    for item in group.get("items", []):
                        tx.item(
                            item["oid"],
                            value=item.get("value") or None,
                            specify=item.get("specify") or None,
                            query=item.get("query") or None,
                            query_status=statuses.get(
                                item.get("query_status", "(none)")
                            ),
                            query_recipient=recipients.get(
                                item.get("query_recipient", "(none)")
                            ),
                        )
    return tx


def _render_report(report: DiagnosticReport) -> None:
    """Render a DiagnosticReport as structured Streamlit components."""
    severity_colour = "🔴" if report.severity == "error" else "🟡"
    category_label = report.category.replace("_", " ").title()
    st.markdown(f"### {severity_colour} {category_label}")

    if report.requested:
        st.markdown("**Requested**")
        for k, v in report.requested.items():
            st.code(f"{k}: {v}", language=None)

    if report.evidence:
        st.markdown("**Evidence**")
        for k, v in report.evidence.items():
            st.code(f"{k}: {v}", language=None)

    if report.recommendation:
        st.info(report.recommendation)

    retry_label = (
        "✅ Safe to retry" if report.safe_to_retry else "❌ Do not retry automatically"
    )
    st.caption(retry_label)


def _get_or_build_client() -> RWSClient | None:
    """Return the RWSClient from session state, or None if not configured."""
    return st.session_state.client


# ---------------------------------------------------------------------------
# Sidebar — credentials (no ping, saved immediately on Save)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚗️ RaveForge")
    st.markdown("---")
    st.subheader("RWS Credentials")
    st.caption(
        "Enter the domain only — no path. "
        "Credentials are validated on the first RWS call."
    )

    base_url = st.text_input(
        "Base URL",
        value=(
            st.session_state.client.base_url
            if st.session_state.client is not None
            else ""
        ),
        placeholder="https://innovate.mdsol.com",
        help="Domain only, e.g. https://innovate.mdsol.com",
    )
    username = st.text_input(
        "Username",
        value=(
            st.session_state.client.auth.username
            if st.session_state.client is not None
            else ""
        ),
    )
    password = st.text_input("Password", type="password")

    if st.button("Save Credentials", use_container_width=True, type="primary"):
        if not base_url or not username or not password:
            st.error("All three fields are required.")
        else:
            st.session_state.client = RWSClient(
                base_url=base_url.rstrip("/"),
                username=username,
                password=password,
            )
            st.success("✅ Credentials saved — ready to call RWS.")

    if st.session_state.client is not None:
        st.info(
            f"🟢 **{st.session_state.client.auth.username}** → "
            f"`{st.session_state.client.base_url}`"
        )
    else:
        st.warning("🔴 No credentials saved yet.")

    if st.button("Clear Credentials", use_container_width=True, type="secondary"):
        st.session_state.client = None
        st.rerun()

    st.markdown("---")
    st.caption("Powered by [RaveForge](https://github.com/mnouira02/raveforge)")


# ---------------------------------------------------------------------------
# Main — tabs
# ---------------------------------------------------------------------------

tab_builder, tab_validate, tab_submit, tab_browser = st.tabs(
    ["🏗️ Builder", "✅ Validate", "🚀 Submit", "🔍 Study Browser"]
)


# ===========================================================================
# TAB 1 — Transaction Builder
# ===========================================================================

with tab_builder:
    st.header("Transaction Builder")
    st.caption(
        "Build your ODM payload subject by subject. "
        "The live XML preview updates as you type."
    )

    col_form, col_preview = st.columns([3, 2], gap="large")

    with col_form:
        study_oid = st.text_input(
            "Study OID",
            key="study_oid",
            placeholder="e.g. Oncology_Phase_II_Prod",
        )

        st.markdown("---")
        st.subheader("Subjects")

        if st.button("＋ Add Subject"):
            st.session_state.subjects.append({
                "key": "",
                "site_oid": "",
                "action": "(none)",
                "events": [],
            })

        for s_idx, subj in enumerate(st.session_state.subjects):
            with st.expander(
                f"Subject {s_idx + 1}: {subj['key'] or '(unnamed)'}",
                expanded=True,
            ):
                c1, c2, c3 = st.columns([2, 2, 1])
                subj["key"] = c1.text_input(
                    "SubjectKey", value=subj["key"],
                    key=f"s{s_idx}_key",
                )
                subj["site_oid"] = c2.text_input(
                    "SiteOID", value=subj["site_oid"],
                    key=f"s{s_idx}_site",
                )
                subj["action"] = c3.selectbox(
                    "Action", list(_action_options().keys()),
                    index=0, key=f"s{s_idx}_action",
                )

                if st.button("＋ Add Event", key=f"add_ev_{s_idx}"):
                    subj["events"].append({
                        "oid": "", "repeat_key": "", "action": "(none)",
                        "forms": [],
                    })

                for e_idx, event in enumerate(subj.get("events", [])):
                    with st.container():
                        st.markdown(f"**Event {e_idx + 1}**")
                        ec1, ec2, ec3 = st.columns([2, 1, 1])
                        event["oid"] = ec1.text_input(
                            "StudyEventOID", value=event["oid"],
                            key=f"s{s_idx}e{e_idx}_oid",
                        )
                        event["repeat_key"] = ec2.text_input(
                            "RepeatKey", value=event.get("repeat_key", ""),
                            key=f"s{s_idx}e{e_idx}_rk",
                        )
                        event["action"] = ec3.selectbox(
                            "Action", list(_action_options().keys()),
                            index=0, key=f"s{s_idx}e{e_idx}_action",
                        )

                        if st.button("＋ Add Form", key=f"add_form_{s_idx}_{e_idx}"):
                            event["forms"].append({
                                "oid": "", "repeat_key": "", "action": "(none)",
                                "item_groups": [],
                            })

                        for f_idx, form in enumerate(event.get("forms", [])):
                            st.markdown(f"*Form {f_idx + 1}*")
                            fc1, fc2, fc3 = st.columns([2, 1, 1])
                            form["oid"] = fc1.text_input(
                                "FormOID", value=form["oid"],
                                key=f"s{s_idx}e{e_idx}f{f_idx}_oid",
                            )
                            form["repeat_key"] = fc2.text_input(
                                "RepeatKey", value=form.get("repeat_key", ""),
                                key=f"s{s_idx}e{e_idx}f{f_idx}_rk",
                            )
                            form["action"] = fc3.selectbox(
                                "Action", list(_action_options().keys()),
                                index=0,
                                key=f"s{s_idx}e{e_idx}f{f_idx}_action",
                            )

                            if st.button(
                                "＋ Add ItemGroup",
                                key=f"add_ig_{s_idx}_{e_idx}_{f_idx}",
                            ):
                                form["item_groups"].append({
                                    "oid": "", "repeat_key": "",
                                    "specified_items_only": False,
                                    "action": "(none)", "items": [],
                                })

                            for g_idx, group in enumerate(
                                form.get("item_groups", [])
                            ):
                                st.markdown(f"ItemGroup {g_idx + 1}")
                                gc1, gc2, gc3, gc4 = st.columns([2, 1, 1, 1])
                                group["oid"] = gc1.text_input(
                                    "ItemGroupOID", value=group["oid"],
                                    key=f"s{s_idx}e{e_idx}f{f_idx}g{g_idx}_oid",
                                )
                                group["repeat_key"] = gc2.text_input(
                                    "RepeatKey",
                                    value=group.get("repeat_key", ""),
                                    key=f"s{s_idx}e{e_idx}f{f_idx}g{g_idx}_rk",
                                )
                                group["specified_items_only"] = gc3.checkbox(
                                    "SpecifiedItemsOnly",
                                    value=group.get("specified_items_only", False),
                                    key=(
                                        f"s{s_idx}e{e_idx}f{f_idx}"
                                        f"g{g_idx}_sio"
                                    ),
                                )
                                group["action"] = gc4.selectbox(
                                    "Action", list(_action_options().keys()),
                                    index=0,
                                    key=(
                                        f"s{s_idx}e{e_idx}f{f_idx}"
                                        f"g{g_idx}_action"
                                    ),
                                )

                                if st.button(
                                    "＋ Add Item",
                                    key=(
                                        f"add_item_{s_idx}_{e_idx}"
                                        f"_{f_idx}_{g_idx}"
                                    ),
                                ):
                                    group["items"].append({
                                        "oid": "", "value": "",
                                        "specify": "", "query": "",
                                        "query_status": "(none)",
                                        "query_recipient": "(none)",
                                    })

                                for i_idx, item in enumerate(
                                    group.get("items", [])
                                ):
                                    ic1, ic2, ic3 = st.columns([1, 1, 1])
                                    item["oid"] = ic1.text_input(
                                        "ItemOID", value=item["oid"],
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_oid"
                                        ),
                                    )
                                    item["value"] = ic2.text_input(
                                        "Value", value=item.get("value", ""),
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_val"
                                        ),
                                    )
                                    item["specify"] = ic3.text_input(
                                        "Specify",
                                        value=item.get("specify", ""),
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_spec"
                                        ),
                                    )
                                    qc1, qc2, qc3 = st.columns([2, 1, 1])
                                    item["query"] = qc1.text_input(
                                        "Query text",
                                        value=item.get("query", ""),
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_q"
                                        ),
                                    )
                                    item["query_status"] = qc2.selectbox(
                                        "Query Status",
                                        list(_query_status_options().keys()),
                                        index=0,
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_qs"
                                        ),
                                    )
                                    item["query_recipient"] = qc3.selectbox(
                                        "Query Recipient",
                                        list(_query_recipient_options().keys()),
                                        index=0,
                                        key=(
                                            f"s{s_idx}e{e_idx}f{f_idx}"
                                            f"g{g_idx}i{i_idx}_qr"
                                        ),
                                    )
                                    st.markdown("---")

        if st.button("🗑️ Clear all subjects", type="secondary"):
            st.session_state.subjects = []
            st.session_state.tx = None
            st.rerun()

    with col_preview:
        st.subheader("Live XML Preview")
        if study_oid and st.session_state.subjects:
            try:
                preview_tx = _build_transaction(
                    study_oid, st.session_state.subjects
                )
                st.session_state.tx = preview_tx
                xml_str = preview_tx.build_pretty()
                st.code(xml_str, language="xml")
            except Exception as exc:
                st.warning(f"Cannot render preview: {exc}")
        else:
            st.info(
                "Enter a Study OID and add at least one subject "
                "to see the XML preview."
            )


# ===========================================================================
# TAB 2 — Validate
# ===========================================================================

with tab_validate:
    st.header("Validate Transaction")
    st.caption(
        "Runs all structural rules against the current transaction. "
        "Strict mode treats warnings as errors."
    )

    strict = st.toggle("Strict mode", value=True)

    if st.button("Run Validation", type="primary"):
        study_oid_v = st.session_state.get("study_oid", "")
        if not study_oid_v:
            st.warning("Set a Study OID in the Builder tab first.")
        else:
            try:
                tx_v = _build_transaction(
                    study_oid_v, st.session_state.subjects
                )
                issues = validate(tx_v, strict=False)
                st.session_state.validation_issues = issues

                blocking = [
                    i for i in issues
                    if str(i.severity) in ("Severity.ERROR", "ERROR")
                    or (
                        strict
                        and str(i.severity) in ("Severity.WARNING", "WARNING")
                    )
                ]

                if not issues:
                    st.success("✅ Transaction is valid — no issues found.")
                elif blocking:
                    st.error(
                        f"{len(blocking)} blocking issue(s) found "
                        f"({'strict' if strict else 'non-strict'} mode)."
                    )
                else:
                    st.warning(
                        f"{len(issues)} warning(s) found "
                        "(not blocking in non-strict mode)."
                    )

                if issues:
                    rows = [
                        {
                            "Severity": str(i.severity.value),
                            "Code": i.code,
                            "Location": i.location or "—",
                            "Message": i.message,
                        }
                        for i in issues
                    ]
                    st.dataframe(rows, use_container_width=True)

            except ValidationError as ve:
                st.error(str(ve))
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
    else:
        if st.session_state.validation_issues:
            st.info("Showing results from last validation run.")
            rows = [
                {
                    "Severity": str(i.severity.value),
                    "Code": i.code,
                    "Location": i.location or "—",
                    "Message": i.message,
                }
                for i in st.session_state.validation_issues
            ]
            st.dataframe(rows, use_container_width=True)


# ===========================================================================
# TAB 3 — Submit
# ===========================================================================

with tab_submit:
    st.header("Submit to RWS")
    st.caption(
        "Posts the current transaction to Rave Web Services. "
        "On failure, the diagnostic layer analyses the error automatically."
    )

    client = _get_or_build_client()
    if client is None:
        st.warning("Save your RWS credentials in the sidebar first.")
    else:
        study_oid_sub = st.session_state.get("study_oid", "")
        if not study_oid_sub or not st.session_state.subjects:
            st.info("Build a transaction in the Builder tab first.")
        else:
            try:
                tx_sub = _build_transaction(
                    study_oid_sub, st.session_state.subjects
                )
            except Exception as exc:
                st.error(f"Could not assemble transaction: {exc}")
                tx_sub = None

            if tx_sub is not None:
                with st.expander("Preview payload before submitting"):
                    st.code(tx_sub.build_pretty(), language="xml")

                if st.button("🚀 Submit", type="primary"):
                    try:
                        validate(tx_sub, strict=True)
                        response = client.post_odm(tx_sub.build())
                        st.success(
                            "✅ Submission accepted by RWS.\n\n"
                            + response
                        )
                        st.session_state.last_report = None
                    except ValidationError as ve:
                        st.error("Transaction failed pre-submit validation:")
                        st.code(str(ve))
                    except RWSError as rws_err:
                        st.error(f"RWS rejected the submission: {rws_err}")
                        try:
                            diag = RaveDiagnostics(client)
                            report = diag.explain_submission_failure(
                                rws_err, transaction=tx_sub
                            )
                            st.session_state.last_report = report
                        except Exception:
                            st.session_state.last_report = None
                    except Exception as exc:
                        st.error(f"Unexpected error: {exc}")

                if st.session_state.last_report is not None:
                    st.markdown("---")
                    st.subheader("Diagnostic Report")
                    _render_report(st.session_state.last_report)


# ===========================================================================
# TAB 4 — Study Browser
# ===========================================================================

with tab_browser:
    st.header("Study Browser")
    st.caption(
        "Browse studies and sites accessible to the configured user. "
        "Read-only — nothing is modified."
    )

    client = _get_or_build_client()
    if client is None:
        st.warning("Save your RWS credentials in the sidebar first.")
    else:
        diag_browser = RaveDiagnostics(client)

        if st.button("Load Studies", type="primary"):
            try:
                studies = diag_browser.get_studies()
                if not studies:
                    st.info("No studies found for this user.")
                else:
                    st.success(f"{len(studies)} study/studies found.")
                    st.session_state["browser_studies"] = studies
            except RWSError as rws_err:
                st.error(f"RWS error: {rws_err}")
            except Exception as exc:
                st.error(f"Failed to load studies: {exc}")

        if st.session_state.get("browser_studies"):
            studies_data = st.session_state["browser_studies"]
            st.dataframe(
                [{"OID": s["oid"], "Name": s["name"]} for s in studies_data],
                use_container_width=True,
            )

            selected_oid = st.selectbox(
                "Select a study to browse its sites",
                options=[s["oid"] for s in studies_data],
                key="browser_selected_study",
            )

            if st.button("Load Sites"):
                try:
                    site_oids = diag_browser.get_sites(selected_oid)
                    if not site_oids:
                        st.info("No sites found for this study.")
                    else:
                        st.success(f"{len(site_oids)} site(s) found.")
                        st.dataframe(
                            [{"SiteOID": s} for s in site_oids],
                            use_container_width=True,
                        )
                except RWSError as rws_err:
                    st.error(f"RWS error: {rws_err}")
                except Exception as exc:
                    st.error(f"Failed to load sites: {exc}")
