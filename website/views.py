from flask import Blueprint, render_template, request, redirect, url_for, session
from functools import wraps
from datetime import datetime
import hashlib
import uuid
from . import supabase

views = Blueprint("views", __name__)

ADMIN_PASSWORD_HASH = "aa85e9f38da6d1e729c080415e4496945425505314b46f2e98013544d4866d8d"


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            if request.headers.get("HX-Request"):
                return "", 401
            return redirect(url_for("views.login"))
        return f(*args, **kwargs)

    return decorated_function


@views.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")

        if hash_password(password) == ADMIN_PASSWORD_HASH:
            session["logged_in"] = True
            return redirect(url_for("views.users"))
        else:
            return render_template("login.html", error="Invalid password")

    return render_template("login.html")


@views.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("views.login"))


@views.route("/")
@login_required
def index():
    return redirect(url_for("views.users"))


@views.route("/users")
@login_required
def users():
    try:
        search = request.args.get("search", "")
        query = supabase.table("profiles").select("*")

        if search:
            query = query.or_(
                f"username.ilike.%{search}%,first_name.ilike.%{search}%,last_name.ilike.%{search}%,email.ilike.%{search}%,ticket_no.ilike.%{search}%"
            )

        result = query.order("created_at", desc=True).execute()

        users_data = []
        for user in result.data:
            user_id = user["id"]

            accounts = (
                supabase.table("user_accounts")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            trans = (
                supabase.table("transactions")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            kyc = (
                supabase.table("kyc_data")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .execute()
            )
            accs = (
                supabase.table("user_accounts")
                .select("balance")
                .eq("user_id", user_id)
                .execute()
            )

            total_balance = (
                sum(float(acc.get("balance", 0)) for acc in accs.data)
                if accs.data
                else 0
            )

            user["accounts_count"] = accounts.count or 0
            user["transactions_count"] = trans.count or 0
            user["kyc_count"] = kyc.count or 0
            user["total_balance"] = total_balance
            users_data.append(user)

        return render_template("users.html", users=users_data, search=search)
    except Exception as e:
        print(f"ERROR in /users: {str(e)}")
        import traceback

        traceback.print_exc()
        return render_template("users.html", users=[], search="", error=str(e))


@views.route("/users/<user_id>")
@login_required
def user_detail(user_id):
    try:
        profile_result = (
            supabase.table("profiles").select("*").eq("id", user_id).execute()
        )

        if not profile_result.data or len(profile_result.data) == 0:
            return redirect(url_for("views.users"))

        profile = profile_result.data[0]
        return render_template("user_detail.html", user=profile, user_id=user_id)
    except Exception as e:
        print(f"ERROR in user_detail for user {user_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return redirect(url_for("views.users"))


@views.route("/users/<user_id>/delete", methods=["POST"])
@login_required
def delete_user(user_id):
    try:
        supabase.table("profiles").delete().eq("id", user_id).execute()
        try:
            supabase.auth.admin.delete_user(user_id)
        except:
            pass
        return redirect(url_for("views.users"))
    except Exception as e:
        print(f"ERROR deleting user {user_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return redirect(url_for("views.users"))


@views.route("/users/<user_id>/profile")
@login_required
def user_profile_section(user_id):
    try:
        profile_result = (
            supabase.table("profiles").select("*").eq("id", user_id).execute()
        )

        if not profile_result.data or len(profile_result.data) == 0:
            return '<div class="error-box">Profile not found</div>', 404

        profile = profile_result.data[0]
        return render_template(
            "partials/profile_section.html", profile=profile, user_id=user_id
        )
    except Exception as e:
        print(f"ERROR in user_profile_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/profile/update", methods=["POST"])
@login_required
def update_profile_field(user_id):
    try:
        field = request.form.get("field")
        value = request.form.get("value")

        supabase.table("profiles").update({field: value}).eq("id", user_id).execute()

        profile_result = (
            supabase.table("profiles").select("*").eq("id", user_id).execute()
        )

        if not profile_result.data or len(profile_result.data) == 0:
            return '<div class="error-box">Profile not found</div>', 404

        profile = profile_result.data[0]
        return render_template(
            "partials/profile_section.html",
            profile=profile,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR updating profile for user {user_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/accounts")
@login_required
def user_accounts_section(user_id):
    try:
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )
        return render_template(
            "partials/accounts_section.html", accounts=accounts.data, user_id=user_id
        )
    except Exception as e:
        print(f"ERROR in user_accounts_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/accounts/<account_id>/update", methods=["POST"])
@login_required
def update_account_field(user_id, account_id):
    try:
        field = request.form.get("field")
        value = request.form.get("value")

        supabase.table("user_accounts").update({field: value}).eq(
            "id", account_id
        ).execute()
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )

        return render_template(
            "partials/accounts_section.html",
            accounts=accounts.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR updating account {account_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/accounts/<account_id>/update-balance", methods=["POST"])
@login_required
def update_account_balance(user_id, account_id):
    try:
        action = request.form.get("action")
        increment_value = request.form.get("increment", "0")
        decrement_value = request.form.get("decrement", "0")

        account_result = (
            supabase.table("user_accounts").select("*").eq("id", account_id).execute()
        )

        if not account_result.data or len(account_result.data) == 0:
            return '<div class="error-box">Account not found</div>', 404

        account = account_result.data[0]
        old_balance = float(account.get("balance", 0))

        if action == "increment":
            amount = float(increment_value) if increment_value else 0
            new_balance = old_balance + amount
            transaction_type = "credit"
            description = f"+${amount:.2f}"
        elif action == "decrement":
            amount = float(decrement_value) if decrement_value else 0
            new_balance = old_balance - amount
            transaction_type = "debit"
            description = f"-${amount:.2f}"
        else:
            return '<div class="error-box">Invalid action</div>', 400

        if new_balance < 0:
            return '<div class="error-box">Insufficient balance</div>', 400

        supabase.table("user_accounts").update({"balance": new_balance}).eq(
            "id", account_id
        ).execute()

        if amount > 0:
            now = datetime.utcnow()
            transaction_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "account_id": account_id,
                "transaction_type": transaction_type,
                "description": description,
                "amount": amount,
                "status": "completed",
                "transaction_date": now.date().isoformat(),
                "transaction_time": now.time().isoformat(),
            }
            supabase.table("transactions").insert(transaction_data).execute()

        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )
        return render_template(
            "partials/accounts_section.html",
            accounts=accounts.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR updating account balance: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/accounts/<account_id>/delete", methods=["POST"])
@login_required
def delete_account(user_id, account_id):
    try:
        supabase.table("user_accounts").delete().eq("id", account_id).execute()
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )

        return render_template(
            "partials/accounts_section.html",
            accounts=accounts.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR deleting account {account_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/transactions")
@login_required
def user_transactions_section(user_id):
    try:
        transactions = (
            supabase.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("transaction_date", desc=True)
            .execute()
        )
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )
        return render_template(
            "partials/transactions_section.html",
            transactions=transactions.data,
            user_id=user_id,
            accounts=accounts.data,
        )
    except Exception as e:
        print(f"ERROR in user_transactions_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/transactions/<trans_id>/update", methods=["POST"])
@login_required
def update_transaction_field(user_id, trans_id):
    try:
        field = request.form.get("field")
        value = request.form.get("value")

        trans_result = (
            supabase.table("transactions").select("*").eq("id", trans_id).execute()
        )
        if not trans_result.data or len(trans_result.data) == 0:
            return '<div class="error-box">Transaction not found</div>', 404

        transaction = trans_result.data[0]
        old_status = transaction.get("status")

        supabase.table("transactions").update({field: value}).eq(
            "id", trans_id
        ).execute()

        if (
            field == "status"
            and value in ["completed", "approved"]
            and old_status == "pending"
        ):
            handle_transaction_balance_update(transaction, user_id)

        transactions = (
            supabase.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("transaction_date", desc=True)
            .execute()
        )
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )

        return render_template(
            "partials/transactions_section.html",
            transactions=transactions.data,
            user_id=user_id,
            accounts=accounts.data,
            success=True,
        )
    except Exception as e:
        print(f"ERROR updating transaction {trans_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


def handle_transaction_balance_update(transaction, user_id):
    try:
        account_id = transaction.get("account_id")
        transaction_type = (transaction.get("transaction_type") or "").strip().lower()
        amount = float(transaction.get("amount", 0))

        if not account_id:
            accounts = (
                supabase.table("user_accounts")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            if accounts.data:
                account_id = accounts.data[0]["id"]
            else:
                return

        if amount <= 0:
            return

        account_result = (
            supabase.table("user_accounts").select("*").eq("id", account_id).execute()
        )
        if not account_result.data or len(account_result.data) == 0:
            return

        account = account_result.data[0]
        current_balance = float(account.get("balance", 0))

        if transaction_type == "credit":
            new_balance = current_balance + amount
        elif transaction_type == "debit":
            new_balance = current_balance - amount
            if new_balance < 0:
                return
        else:
            return

        supabase.table("user_accounts").update({"balance": new_balance}).eq(
            "id", account_id
        ).execute()

    except Exception as e:
        print(f"ERROR handling balance update: {str(e)}")
        import traceback

        traceback.print_exc()


@views.route("/users/<user_id>/transactions/<trans_id>/delete", methods=["POST"])
@login_required
def delete_transaction(user_id, trans_id):
    try:
        supabase.table("transactions").delete().eq("id", trans_id).execute()
        transactions = (
            supabase.table("transactions")
            .select("*")
            .eq("user_id", user_id)
            .order("transaction_date", desc=True)
            .execute()
        )
        accounts = (
            supabase.table("user_accounts").select("*").eq("user_id", user_id).execute()
        )

        return render_template(
            "partials/transactions_section.html",
            transactions=transactions.data,
            user_id=user_id,
            accounts=accounts.data,
            success=True,
        )
    except Exception as e:
        print(f"ERROR deleting transaction {trans_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/kyc")
@login_required
def user_kyc_section(user_id):
    try:
        kyc = (
            supabase.table("kyc_data")
            .select("*")
            .eq("user_id", user_id)
            .order("submitted_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/kyc_section.html", kyc_data=kyc.data, user_id=user_id
        )
    except Exception as e:
        print(f"ERROR in user_kyc_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/kyc/update", methods=["POST"])
@login_required
def update_kyc_field(user_id):
    try:
        field = request.form.get("field")
        value = request.form.get("value")

        kyc = supabase.table("kyc_data").select("*").eq("user_id", user_id).execute()

        if kyc.data:
            supabase.table("kyc_data").update({field: value}).eq(
                "user_id", user_id
            ).execute()
        else:
            supabase.table("kyc_data").insert(
                {"user_id": user_id, field: value}
            ).execute()

        kyc = (
            supabase.table("kyc_data")
            .select("*")
            .eq("user_id", user_id)
            .order("submitted_at", desc=True)
            .execute()
        )

        return render_template(
            "partials/kyc_section.html",
            kyc_data=kyc.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR updating KYC: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/kyc/create", methods=["POST"])
@login_required
def create_kyc(user_id):
    try:
        kyc = supabase.table("kyc_data").select("*").eq("user_id", user_id).execute()

        if not kyc.data:
            supabase.table("kyc_data").insert({"user_id": user_id}).execute()

        kyc = (
            supabase.table("kyc_data")
            .select("*")
            .eq("user_id", user_id)
            .order("submitted_at", desc=True)
            .execute()
        )

        return render_template(
            "partials/kyc_section.html",
            kyc_data=kyc.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR creating KYC: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/banks")
@login_required
def user_banks_section(user_id):
    try:
        banks = (
            supabase.table("user_linked_banks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/bank_section.html", banks=banks.data, user_id=user_id
        )
    except Exception as e:
        print(f"ERROR in user_banks_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/banks/<bank_id>/approve", methods=["POST"])
@login_required
def approve_bank(user_id, bank_id):
    try:
        supabase.table("user_linked_banks").update({"status": "approved"}).eq(
            "id", bank_id
        ).execute()

        banks = (
            supabase.table("user_linked_banks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/bank_section.html",
            banks=banks.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR approving bank {bank_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/banks/<bank_id>/delete", methods=["POST"])
@login_required
def delete_bank(user_id, bank_id):
    try:
        supabase.table("user_linked_banks").delete().eq("id", bank_id).execute()
        banks = (
            supabase.table("user_linked_banks")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/bank_section.html",
            banks=banks.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR deleting bank {bank_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/cards")
@login_required
def user_cards_section(user_id):
    try:
        cards = (
            supabase.table("virtual_cards")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/cards_section.html", cards=cards.data, user_id=user_id
        )
    except Exception as e:
        print(f"ERROR in user_cards_section: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/cards/<card_id>/approve-creation", methods=["POST"])
@login_required
def approve_card_creation(user_id, card_id):
    try:
        supabase.table("virtual_cards").update(
            {"creation_status": "approved", "status": "approved"}
        ).eq("id", card_id).execute()

        cards = (
            supabase.table("virtual_cards")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/cards_section.html",
            cards=cards.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR approving card creation {card_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/cards/<card_id>/approve-delete", methods=["POST"])
@login_required
def approve_card_deletion(user_id, card_id):
    try:
        supabase.table("virtual_cards").delete().eq("id", card_id).execute()

        cards = (
            supabase.table("virtual_cards")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/cards_section.html",
            cards=cards.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR approving card deletion {card_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/cards/<card_id>/cancel-delete", methods=["POST"])
@login_required
def cancel_card_deletion(user_id, card_id):
    try:
        supabase.table("virtual_cards").update({"deletion_status": None}).eq(
            "id", card_id
        ).execute()

        cards = (
            supabase.table("virtual_cards")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/cards_section.html",
            cards=cards.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR canceling card deletion {card_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/cards/<card_id>/delete", methods=["POST"])
@login_required
def delete_card(user_id, card_id):
    try:
        supabase.table("virtual_cards").delete().eq("id", card_id).execute()
        cards = (
            supabase.table("virtual_cards")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/cards_section.html",
            cards=cards.data,
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR deleting card {card_id}: {str(e)}")
        import traceback

        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


# ─── Gift Card Deposits ───────────────────────────────────────────────


def _delete_gift_card_storage_image(image_url):
    """Extract file path from public URL and delete from Supabase storage."""
    try:
        if not image_url:
            return
        marker = "/object/public/app-assets/"
        idx = image_url.find(marker)
        if idx == -1:
            return
        file_path = image_url[idx + len(marker):]
        supabase.storage.from_("app-assets").remove([file_path])
    except Exception as e:
        print(f"WARNING: Could not delete storage file: {e}")


@views.route("/gift-cards")
@login_required
def gift_cards():
    try:
        result = (
            supabase.table("gift_card_deposits")
            .select("*")
            .order("submitted_at", desc=True)
            .execute()
        )
        deposits = result.data or []

        enriched = []
        for dep in deposits:
            uid = dep.get("user_id")
            profile = None
            if uid:
                pr = supabase.table("profiles").select("username, first_name, last_name, email").eq("id", uid).execute()
                if pr.data:
                    profile = pr.data[0]
            enriched.append({**dep, "profile": profile})

        return render_template("gift_cards.html", deposits=enriched)
    except Exception as e:
        print(f"ERROR in gift_cards: {str(e)}")
        import traceback
        traceback.print_exc()
        return render_template("gift_cards.html", deposits=[], error=str(e))


@views.route("/gift-cards/<deposit_id>/delete", methods=["POST"])
@login_required
def delete_gift_card(deposit_id):
    try:
        dep = supabase.table("gift_card_deposits").select("image_url").eq("id", deposit_id).execute()
        if dep.data:
            _delete_gift_card_storage_image(dep.data[0].get("image_url"))
        supabase.table("gift_card_deposits").delete().eq("id", deposit_id).execute()
        return redirect(url_for("views.gift_cards"))
    except Exception as e:
        print(f"ERROR deleting gift card {deposit_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(url_for("views.gift_cards"))


@views.route("/users/<user_id>/gift-cards")
@login_required
def user_gift_cards_section(user_id):
    try:
        result = (
            supabase.table("gift_card_deposits")
            .select("*")
            .eq("user_id", user_id)
            .order("submitted_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/gift_cards_section.html",
            deposits=result.data or [],
            user_id=user_id,
        )
    except Exception as e:
        print(f"ERROR in user_gift_cards_section: {str(e)}")
        import traceback
        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500


@views.route("/users/<user_id>/gift-cards/<deposit_id>/delete", methods=["POST"])
@login_required
def delete_user_gift_card(user_id, deposit_id):
    try:
        dep = supabase.table("gift_card_deposits").select("image_url").eq("id", deposit_id).execute()
        if dep.data:
            _delete_gift_card_storage_image(dep.data[0].get("image_url"))
        supabase.table("gift_card_deposits").delete().eq("id", deposit_id).execute()
        deposits = (
            supabase.table("gift_card_deposits")
            .select("*")
            .eq("user_id", user_id)
            .order("submitted_at", desc=True)
            .execute()
        )
        return render_template(
            "partials/gift_cards_section.html",
            deposits=deposits.data or [],
            user_id=user_id,
            success=True,
        )
    except Exception as e:
        print(f"ERROR deleting gift card {deposit_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return f'<div class="error-box">Error: {str(e)}</div>', 500
