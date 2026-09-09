import streamlit as st
from utils.db import init_db, get_setting, set_setting, run_query
from utils.auth import require_role, render_sidebar_user_box, current_user, hash_password, ROLES, ROLE_LABELS

st.set_page_config(page_title="Settings · Jewellery ERP", page_icon="⚙️", layout="wide")
init_db()
require_role("admin")
render_sidebar_user_box()
st.title("⚙️ Settings")

tab_company, tab_tax, tab_users, tab_data = st.tabs(
    ["🏢 Company Info", "💰 Tax & Currency", "👥 Users & Roles", "🗄️ Data Management"]
)

with tab_company:
    with st.form("company_settings"):
        company_name = st.text_input("Company Name", value=get_setting("company_name"))
        gst_number = st.text_input("GST Number", value=get_setting("gst_number"))
        address = st.text_area("Address", value=get_setting("address"))
        phone = st.text_input("Phone", value=get_setting("phone"))
        email = st.text_input("Email", value=get_setting("email"))
        if st.form_submit_button("💾 Save", type="primary"):
            set_setting("company_name", company_name)
            set_setting("gst_number", gst_number)
            set_setting("address", address)
            set_setting("phone", phone)
            set_setting("email", email)
            st.success("Saved ✅")
            st.rerun()

with tab_tax:
    with st.form("tax_settings"):
        currency_symbol = st.text_input("Currency Symbol", value=get_setting("currency_symbol", "₹"))
        gst_rate = st.number_input("Default GST Rate (%)", min_value=0.0, max_value=50.0,
                                    value=float(get_setting("gst_rate", "3") or 3), step=0.5)
        if st.form_submit_button("💾 Save", type="primary"):
            set_setting("currency_symbol", currency_symbol)
            set_setting("gst_rate", str(gst_rate))
            st.success("Saved ✅")
            st.rerun()
    st.caption("In India, hallmarked gold jewellery typically attracts 3% GST (1% making charge GST is "
               "often merged for simplicity) — verify current rates with your accountant.")

with tab_users:
    st.subheader("👥 Team Members")
    users = run_query("SELECT * FROM users ORDER BY created_at", fetch=True)

    if users:
        import pandas as pd
        udf = pd.DataFrame(users)
        udf["role"] = udf["role"].map(lambda r: ROLE_LABELS.get(r, r))
        udf["active"] = udf["active"].map(lambda a: "✅ Active" if a else "⛔ Disabled")
        show = udf[["username", "full_name", "role", "active", "last_login"]].copy()
        show.columns = ["Username", "Full Name", "Role", "Status", "Last Login"]
        st.dataframe(show, hide_index=True, use_container_width=True)

    st.divider()
    st.subheader("➕ Add a team member")
    with st.form("add_user_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        new_username = c1.text_input("Username")
        new_full_name = c2.text_input("Full name")
        c3, c4 = st.columns(2)
        new_password = c3.text_input("Password", type="password")
        new_role = c4.selectbox("Role", ROLES, format_func=lambda r: ROLE_LABELS.get(r, r))
        if st.form_submit_button("💾 Create user", type="primary"):
            if not new_username or not new_password:
                st.error("Username and password are required.")
            else:
                existing = run_query("SELECT id FROM users WHERE username=?", (new_username,), fetchone=True)
                if existing:
                    st.error("That username is already taken.")
                else:
                    run_query(
                        "INSERT INTO users (username, password_hash, full_name, role, active) VALUES (?,?,?,?,1)",
                        (new_username, hash_password(new_password), new_full_name, new_role),
                    )
                    st.success(f"User '{new_username}' created ✅")
                    st.rerun()

    st.divider()
    st.subheader("🔧 Manage existing users")
    if users:
        user_opts = {f"{u['username']} ({ROLE_LABELS.get(u['role'], u['role'])})": u for u in users}
        sel_label = st.selectbox("Select a user", list(user_opts.keys()))
        sel_user = user_opts[sel_label]

        active_admins = [u for u in users if u["role"] == "admin" and u["active"]]
        is_only_admin = sel_user["role"] == "admin" and len(active_admins) <= 1

        mc1, mc2, mc3 = st.columns(3)
        new_role_for_user = mc1.selectbox(
            "Change role",
            ROLES,
            index=ROLES.index(sel_user["role"]) if sel_user["role"] in ROLES else 0,
            format_func=lambda r: ROLE_LABELS.get(r, r),
            key="chg_role",
        )
        if mc1.button("Update role", disabled=is_only_admin and new_role_for_user != "admin"):
            run_query("UPDATE users SET role=? WHERE id=?", (new_role_for_user, sel_user["id"]))
            st.success("Role updated ✅")
            st.rerun()

        toggle_label = "⛔ Deactivate" if sel_user["active"] else "✅ Reactivate"
        if mc2.button(toggle_label, disabled=is_only_admin and sel_user["active"]):
            run_query("UPDATE users SET active=? WHERE id=?", (0 if sel_user["active"] else 1, sel_user["id"]))
            st.success("Status updated ✅")
            st.rerun()

        new_pw = mc3.text_input("Reset password to", type="password", key="reset_pw")
        if mc3.button("Reset password") and new_pw:
            run_query("UPDATE users SET password_hash=? WHERE id=?", (hash_password(new_pw), sel_user["id"]))
            st.success("Password reset ✅")

        if is_only_admin:
            st.caption("⚠️ This is the only active administrator — you can't demote or deactivate this "
                       "account until another active admin exists.")
    else:
        st.caption("No users yet.")

with tab_data:
    st.subheader("Database Overview")
    tables = ["products", "orders", "customers", "suppliers", "purchase_orders",
              "manufacturing_jobs", "invoices", "metal_rates"]
    cols = st.columns(4)
    for i, t in enumerate(tables):
        count = run_query(f"SELECT COUNT(*) as c FROM {t}", fetchone=True)["c"]
        cols[i % 4].metric(t.replace("_", " ").title(), count)

    st.divider()
    st.subheader("⚠️ Danger Zone")
    st.caption("This clears ALL data in the ERP (products, orders, customers, etc). This cannot be undone.")
    confirm = st.checkbox("I understand this will permanently delete all data")
    if st.button("🗑️ Reset Entire Database", disabled=not confirm):
        for t in tables + ["order_items", "purchase_items"]:
            run_query(f"DELETE FROM {t}")
        st.success("Database reset. Refresh the app.")
