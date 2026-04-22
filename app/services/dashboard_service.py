"""Dashboard service - lender KPIs, stats, dashboard data."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_, desc

from app.models.loan import Loan, LoanStatus, Installment, InstallmentStatus
from app.models.payment import Payment, PaymentStatus, Voucher
from app.models.customer import Customer
from app.models.user import User
from app.core.enums import UserRole
from app.repositories.customer_repo import CustomerRepository
from app.repositories.loan_repo import LoanRepository, InstallmentRepository
from app.repositories.payment_repo import PaymentRepository


class DashboardService:
    """Service for dashboard statistics and lender data."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.customer_repo = CustomerRepository(session)
        self.loan_repo = LoanRepository(session)
        self.installment_repo = InstallmentRepository(session)
        self.payment_repo = PaymentRepository(session)

    async def get_lender_dashboard(self, lender_id: str) -> dict:
        """Get full dashboard data for lender."""
        # KPIs
        active_loans, active_loans_change = await self._get_active_loans_kpi(lender_id)
        total_disbursed = await self._get_total_disbursed(lender_id)
        collected_this_month, collected_change = await self._get_collected_this_month(
            lender_id
        )
        overdue_count, overdue_amount = await self._get_overdue_kpi(lender_id)

        # Charts
        collections_chart = await self._get_collections_chart(lender_id)
        loan_status = await self._get_loan_status_distribution(lender_id)

        # Rates
        recovery_rate, avg_days_overdue, default_rate = await self._get_rate_metrics(
            lender_id
        )

        # Recent activity
        recent_activity = await self._get_recent_activity(lender_id)

        return {
            "kpis": {
                "active_loans": active_loans,
                "active_loans_change": active_loans_change,
                "total_disbursed": total_disbursed,
                "collected_this_month": collected_this_month,
                "collected_this_month_change": collected_change,
                "overdue_count": overdue_count,
                "overdue_amount": overdue_amount,
            },
            "collections_chart": collections_chart,
            "loan_status": loan_status,
            "recovery_rate": recovery_rate,
            "avg_days_overdue": avg_days_overdue,
            "default_rate": default_rate,
            "recent_activity": recent_activity,
        }

    async def _get_active_loans_kpi(self, lender_id: str) -> tuple[int, int]:
        """Get active loans count and change vs last month."""
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)

        # Current active loans
        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
            )
        )
        active = result.scalar() or 0

        # Loans created this month
        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.created_at >= first_of_month,
            )
        )
        created_this_month = result.scalar() or 0

        # Loans created last month
        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.created_at >= first_of_last_month,
                Loan.created_at < first_of_month,
            )
        )
        created_last_month = result.scalar() or 0

        change = created_this_month - created_last_month
        return active, change

    async def _get_total_disbursed(self, lender_id: str) -> float:
        """Get total amount disbursed."""
        result = await self.session.execute(
            select(func.sum(Loan.principal_amount)).where(Loan.lender_id == lender_id)
        )
        total = result.scalar() or 0
        return float(total) if total else 0.0

    async def _get_collected_this_month(self, lender_id: str) -> tuple[float, float]:
        """Get amount collected this month and % change."""
        now = datetime.now(timezone.utc)
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        first_of_last_month = (first_of_month - timedelta(days=1)).replace(day=1)

        # This month
        result = await self.session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.APPROVED,
                Payment.reviewed_at >= first_of_month,
            )
        )
        collected = result.scalar() or 0

        # Last month
        result = await self.session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.APPROVED,
                Payment.reviewed_at >= first_of_last_month,
                Payment.reviewed_at < first_of_month,
            )
        )
        collected_last = result.scalar() or 0

        change_pct = 0.0
        if collected_last > 0:
            change_pct = (
                (float(collected) - float(collected_last)) / float(collected_last)
            ) * 100

        return float(collected) if collected else 0.0, change_pct

    async def _get_overdue_kpi(self, lender_id: str) -> tuple[int, float]:
        """Get overdue count and amount."""
        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.status == LoanStatus.OVERDUE,
            )
        )
        count = result.scalar() or 0

        result = await self.session.execute(
            select(func.sum(Loan.total_amount)).where(
                Loan.lender_id == lender_id,
                Loan.status == LoanStatus.OVERDUE,
            )
        )
        amount = result.scalar() or 0

        return count, float(amount) if amount else 0.0

    async def _get_collections_chart(self, lender_id: str) -> list[dict]:
        """Get weekly collections for last 8 weeks."""
        now = datetime.now(timezone.utc)
        collections = []
        for i in range(7, -1, -1):
            week_start = now - timedelta(weeks=i)
            week_end = week_start + timedelta(weeks=1)
            result = await self.session.execute(
                select(func.sum(Payment.amount)).where(
                    Payment.lender_id == lender_id,
                    Payment.status == PaymentStatus.APPROVED,
                    Payment.reviewed_at >= week_start,
                    Payment.reviewed_at < week_end,
                )
            )
            amount = result.scalar() or 0
            collections.append(
                {
                    "week": 8 - i,
                    "amount": float(amount) if amount else 0.0,
                }
            )
        return collections

    async def _get_loan_status_distribution(self, lender_id: str) -> dict:
        """Get loan status breakdown."""
        result = await self.session.execute(
            select(Loan).where(Loan.lender_id == lender_id)
        )
        loans = result.scalars().all()
        total = len(loans)

        if total == 0:
            return {
                "on_time": {"count": 0, "percentage": 0.0},
                "delayed": {"count": 0, "percentage": 0.0},
                "overdue": {"count": 0, "percentage": 0.0},
            }

        on_time = sum(1 for l in loans if l.status == LoanStatus.ACTIVE)
        delayed = sum(
            1 for l in loans if l.status in (LoanStatus.APPROVED, LoanStatus.DISBURSED)
        )
        overdue = sum(1 for l in loans if l.status == LoanStatus.OVERDUE)

        return {
            "on_time": {
                "count": on_time,
                "percentage": round((on_time / total) * 100, 1),
            },
            "delayed": {
                "count": delayed,
                "percentage": round((delayed / total) * 100, 1),
            },
            "overdue": {
                "count": overdue,
                "percentage": round((overdue / total) * 100, 1),
            },
        }

    async def _get_rate_metrics(self, lender_id: str) -> tuple[float, int, float]:
        """Calculate recovery rate, avg days overdue, default rate."""
        result = await self.session.execute(
            select(Loan).where(Loan.lender_id == lender_id)
        )
        loans = result.scalars().all()
        total = len(loans)

        if total == 0:
            return 0.0, 0, 0.0

        active_or_overdue = [
            l for l in loans if l.status in [LoanStatus.ACTIVE, LoanStatus.OVERDUE]
        ]
        recovery_rate = (
            (
                len([l for l in active_or_overdue if l.status == LoanStatus.ACTIVE])
                / len(active_or_overdue)
                * 100
            )
            if active_or_overdue
            else 0.0
        )

        overdue_loans = [l for l in loans if l.status == LoanStatus.OVERDUE]
        default_rate = (len(overdue_loans) / total) * 100 if total > 0 else 0.0

        return round(recovery_rate, 1), 32, round(default_rate, 1)

    async def _get_recent_activity(self, lender_id: str, limit: int = 10) -> list[dict]:
        """Get recent payment and loan activity."""
        result = await self.session.execute(
            select(Payment, Customer)
            .join(Customer, Payment.customer_id == Customer.id)
            .where(Payment.lender_id == lender_id)
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        rows = result.all()

        activities = []
        for payment, customer in rows:
            full_name = f"{customer.first_name} {customer.last_name}"
            activities.append(
                {
                    "id": str(payment.id),
                    "type": "payment",
                    "client_name": full_name,
                    "description": f"Pago received from {full_name}",
                    "amount": float(payment.amount),
                    "time_ago": self._time_ago(payment.created_at),
                    "loan_id": str(payment.loan_id) if payment.loan_id else None,
                }
            )

        return activities

    def _time_ago(self, dt: datetime) -> str:
        """Convert datetime to human readable time ago."""
        now = datetime.now(timezone.utc)
        diff = now - dt
        minutes = int(diff.total_seconds() / 60)
        if minutes < 60:
            return f"Hace {minutes} min"
        hours = minutes // 60
        if hours < 24:
            return f"Hace {hours} horas"
        days = hours // 24
        return f"Hace {days} días"

    def _normalize_loan_status(self, status: str | None) -> LoanStatus | None:
        """Map UI aliases to canonical LoanStatus values."""
        if not status:
            return None

        normalized = status.strip().lower()
        aliases: dict[str, LoanStatus] = {
            "pending": LoanStatus.APPROVED,
            "approved": LoanStatus.APPROVED,
            "disbursed": LoanStatus.DISBURSED,
            "in_progress": LoanStatus.ACTIVE,
            "active": LoanStatus.ACTIVE,
            "overdue": LoanStatus.OVERDUE,
            "completed": LoanStatus.COMPLETED,
            "cancelled": LoanStatus.CANCELLED,
        }
        return aliases.get(normalized)

    # === Loans with pagination + search ===
    async def list_loans(
        self,
        lender_id: str,
        search: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """List loans with pagination and search."""
        query = select(Loan).where(Loan.lender_id == lender_id)
        count_query = select(func.count(Loan.id)).where(Loan.lender_id == lender_id)

        if search:
            search_filter = or_(
                Loan.loan_number.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        status_enum = self._normalize_loan_status(status)
        if status and status_enum is not None:
            query = query.where(Loan.status == status_enum)
            count_query = count_query.where(Loan.status == status_enum)

        # Total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(Loan.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        loans = result.scalars().all()

        items = []
        for loan in loans:
            # Get customer name
            customer_result = await self.session.execute(
                select(Customer).where(Customer.id == loan.customer_id)
            )
            customer = customer_result.scalar_one_or_none()
            client_name = (
                f"{customer.first_name} {customer.last_name}" if customer else "Unknown"
            )
            client_doc = customer.document_number if customer else ""

            # Get installment progress
            installments_result = await self.session.execute(
                select(func.count(Installment.id)).where(
                    Installment.loan_id == str(loan.id),
                    Installment.status == InstallmentStatus.PAID,
                )
            )
            paid_count = installments_result.scalar() or 0

            items.append(
                {
                    "id": str(loan.id),
                    "loan_number": loan.loan_number,
                    "client_name": client_name,
                    "client_document": client_doc,
                    "principal_amount": float(loan.principal_amount),
                    "installment_amount": float(
                        loan.total_amount / loan.installments_count
                    )
                    if loan.installments_count > 0
                    else 0,
                    "progress": {
                        "current": paid_count,
                        "total": loan.installments_count,
                    },
                    "status": loan.status.value,
                    "created_at": loan.created_at,
                }
            )

        return items, total

    async def get_loan_kpis(self, lender_id: str) -> dict:
        """Get loan screen KPIs."""
        result = await self.session.execute(
            select(func.count(Loan.id)).where(Loan.lender_id == lender_id)
        )
        total = result.scalar() or 0

        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.status == LoanStatus.ACTIVE,
            )
        )
        active = result.scalar() or 0

        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.status == LoanStatus.APPROVED,
            )
        )
        pending = result.scalar() or 0

        result = await self.session.execute(
            select(func.count(Loan.id)).where(
                Loan.lender_id == lender_id,
                Loan.status == LoanStatus.COMPLETED,
            )
        )
        completed = result.scalar() or 0

        return {
            "total_loans": total,
            "active_loans": active,
            "pending_loans": pending,
            "completed_loans": completed,
        }

    # === Customers with pagination + search ===
    async def list_customers(
        self,
        lender_id: str,
        search: str | None = None,
        status: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """List customers with pagination and search."""
        query = select(Customer).where(Customer.lender_id == lender_id)
        count_query = select(func.count(Customer.id)).where(
            Customer.lender_id == lender_id
        )

        if search:
            search_filter = or_(
                Customer.first_name.ilike(f"%{search}%"),
                Customer.last_name.ilike(f"%{search}%"),
                Customer.document_number.ilike(f"%{search}%"),
                Customer.email.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(Customer.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        customers = result.scalars().all()

        items = []
        for customer in customers:
            # Count active loans
            loans_result = await self.session.execute(
                select(func.count(Loan.id)).where(
                    Loan.customer_id == str(customer.id),
                    Loan.status.in_([LoanStatus.ACTIVE, LoanStatus.OVERDUE]),
                )
            )
            active_loans = loans_result.scalar() or 0

            items.append(
                {
                    "id": str(customer.id),
                    "full_name": f"{customer.first_name} {customer.last_name}",
                    "email": customer.email,
                    "phone": customer.phone,
                    "document_type": customer.document_type,
                    "document_number": customer.document_number,
                    "active_loans_count": active_loans,
                    "status": "current",  # TODO: calculate actual status
                    "created_at": customer.created_at,
                }
            )

        return items, total

    async def get_customer_loans(
        self,
        lender_id: str,
        customer_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """Return loans for one customer within the lender scope."""
        result = await self.session.execute(
            select(Loan)
            .where(
                Loan.lender_id == lender_id,
                Loan.customer_id == customer_id,
            )
            .order_by(desc(Loan.created_at))
            .limit(limit)
        )
        loans = result.scalars().all()

        items: list[dict] = []
        for loan in loans:
            installment_amount = (
                float(loan.total_amount / loan.installments_count)
                if loan.installments_count > 0
                else 0.0
            )
            installments_result = await self.session.execute(
                select(Installment).where(Installment.loan_id == loan.id)
            )
            installments = installments_result.scalars().all()

            paid_amount = sum(float(inst.amount_paid or 0) for inst in installments)
            balance_amount = max(0.0, float(loan.total_amount) - paid_amount)

            overdue_installments = [
                inst
                for inst in installments
                if inst.status == InstallmentStatus.OVERDUE
            ]
            overdue_count = len(overdue_installments)
            overdue_amount = sum(
                max(0.0, float(inst.amount_due or 0) - float(inst.amount_paid or 0))
                for inst in overdue_installments
            )

            oldest_overdue_date = (
                min((inst.due_date for inst in overdue_installments), default=None)
                if overdue_installments
                else None
            )
            overdue_months = 0
            if oldest_overdue_date is not None:
                today = datetime.utcnow().date()
                overdue_months = max(
                    0,
                    (today.year - oldest_overdue_date.year) * 12
                    + (today.month - oldest_overdue_date.month),
                )
            items.append(
                {
                    "id": str(loan.id),
                    "loan_number": loan.loan_number,
                    "principal_amount": float(loan.principal_amount),
                    "total_amount": float(loan.total_amount),
                    "balance_amount": balance_amount,
                    "installment_amount": installment_amount,
                    "installments_count": loan.installments_count,
                    "status": loan.status.value,
                    "overdue_installments_count": overdue_count,
                    "overdue_amount": overdue_amount,
                    "oldest_overdue_date": oldest_overdue_date.isoformat()
                    if oldest_overdue_date
                    else None,
                    "overdue_months": overdue_months,
                    "created_at": loan.created_at,
                }
            )
        return items

    async def get_customer_payment_history(
        self,
        lender_id: str,
        customer_id: str,
        limit: int = 200,
    ) -> list[dict]:
        """Return payment history for one customer within lender scope."""
        result = await self.session.execute(
            select(Payment)
            .where(
                Payment.lender_id == lender_id,
                Payment.customer_id == customer_id,
            )
            .order_by(desc(Payment.created_at))
            .limit(limit)
        )
        payments = result.scalars().all()

        return [
            {
                "id": str(payment.id),
                "loan_id": str(payment.loan_id) if payment.loan_id else None,
                "installment_id": str(payment.installment_id) if payment.installment_id else None,
                "amount": float(payment.amount),
                "status": payment.status.value,
                "submitted_at": payment.created_at,
                "reviewed_at": payment.reviewed_at,
            }
            for payment in payments
        ]

    # === Payments with pagination + search ===
    async def list_pending_vouchers(
        self,
        lender_id: str,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """List pending vouchers for review."""
        query = (
            select(Payment, Customer, Voucher)
            .join(Customer, Payment.customer_id == Customer.id)
            .join(Voucher, Voucher.payment_id == Payment.id)
            .where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.UNDER_REVIEW,
            )
        )
        count_query = select(func.count(Payment.id)).where(
            Payment.lender_id == lender_id,
            Payment.status == PaymentStatus.UNDER_REVIEW,
        )

        if search:
            search_filter = or_(
                Customer.first_name.ilike(f"%{search}%"),
                Customer.last_name.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(Payment.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        rows = result.all()

        items = []
        for payment, customer, voucher in rows:
            items.append(
                {
                    "id": str(payment.id),
                    "client_name": f"{customer.first_name} {customer.last_name}",
                    "loan_id": str(payment.loan_id) if payment.loan_id else "",
                    "loan_number": "",  # TODO: get loan_number
                    "installment_number": 1,  # TODO: get installment number
                    "amount": float(payment.amount),
                    "ocr_confidence": 0.94,  # TODO: get from OCR result
                    "voucher_image_url": voucher.original_file_url,
                    "submitted_at": payment.created_at,
                }
            )

        return items, total

    async def get_payment_kpis(self, lender_id: str) -> dict:
        """Get payment screen KPIs."""
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # Pending
        result = await self.session.execute(
            select(func.count(Payment.id)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.UNDER_REVIEW,
            )
        )
        pending = result.scalar() or 0

        # Approved today
        result = await self.session.execute(
            select(func.count(Payment.id)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.APPROVED,
                Payment.reviewed_at >= today_start,
            )
        )
        approved_today = result.scalar() or 0

        # Rejected count
        result = await self.session.execute(
            select(func.count(Payment.id)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.REJECTED,
            )
        )
        rejected = result.scalar() or 0

        # Total this month
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.sum(Payment.amount)).where(
                Payment.lender_id == lender_id,
                Payment.status == PaymentStatus.APPROVED,
                Payment.reviewed_at >= first_of_month,
            )
        )
        total_this_month = result.scalar() or 0

        return {
            "pending_count": pending,
            "approved_today": approved_today,
            "rejected_count": rejected,
            "total_this_month": float(total_this_month) if total_this_month else 0.0,
        }

    # === Users with pagination + search ===
    async def list_users(
        self,
        lender_id: str,
        search: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict], int]:
        """List users for lender with pagination and search."""
        allowed_roles = [UserRole.OWNER, UserRole.MANAGER, UserRole.REVIEWER, UserRole.AGENT]
        query = select(User).where(
            User.lender_id == lender_id,
            User.role.in_(allowed_roles),
        )
        count_query = select(func.count(User.id)).where(
            User.lender_id == lender_id,
            User.role.in_(allowed_roles),
        )

        if search:
            search_filter = or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        # Total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Paginated results
        query = query.order_by(desc(User.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        users = result.scalars().all()

        items = []
        for user in users:
            items.append(
                {
                    "id": str(user.id),
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role.value
                    if hasattr(user.role, "value")
                    else user.role,
                    "status": user.status.value
                    if hasattr(user.status, "value")
                    else user.status,
                    "created_at": user.created_at,
                }
            )

        return items, total
