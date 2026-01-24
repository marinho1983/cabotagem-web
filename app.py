import os
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, Numeric, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# -----------------------------
# App + DB config (Render)
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

# -----------------------------
# Models
# -----------------------------
class Client(Base):
    __tablename__ = "clients"
    id = Column(Integer, primary_key=True)
    name = Column(String(180), unique=True, nullable=False)

class CostCenter(Base):
    __tablename__ = "cost_centers"
    id = Column(Integer, primary_key=True)
    code = Column(String(30), unique=True, nullable=False)  # ex: "40470"
    name = Column(String(200), nullable=False)              # ex: "Acelen"
    cc_type = Column(String(20), nullable=False)            # CLIENT | OWN | OWNER
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)

    client = relationship("Client")

class Vessel(Base):
    __tablename__ = "vessels"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    vessel_type = Column(String(20), nullable=False)  # OWNED | CHARTERED
    charter_base = Column(String(60), nullable=True)  # ex: PSV240173

class Port(Base):
    __tablename__ = "ports"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String(180), unique=True, nullable=False)
    supplier_type = Column(String(20), nullable=False)  # AGENCY | DIRECT

class Operation(Base):
    __tablename__ = "operations"
    id = Column(Integer, primary_key=True)

    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"), nullable=False)
    vessel_id = Column(Integer, ForeignKey("vessels.id"), nullable=False)
    port_id = Column(Integer, ForeignKey("ports.id"), nullable=False)

    voyage_code = Column(String(120), nullable=False)   # ex: PSV240173-20
    contract_base = Column(String(80), nullable=True)   # PSV240173
    voyage_no = Column(String(30), nullable=True)       # 20

    agency_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)  # agência responsável (opcional)

    operation_key = Column(String(500), unique=True, nullable=False)

    cost_center = relationship("CostCenter")
    vessel = relationship("Vessel")
    port = relationship("Port")
    agency = relationship("Supplier", foreign_keys=[agency_id])

class Entry(Base):
    __tablename__ = "entries"
    id = Column(Integer, primary_key=True)

    operation_id = Column(Integer, ForeignKey("operations.id"), nullable=False)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)

    billing_group = Column(String(10), nullable=False)  # PDA | FDA | DIRECT
    document_type = Column(String(30), nullable=True)   # Antec. | ND | NFE | Boleto | Invoice...
    po = Column(String(80), nullable=True)
    rqa = Column(String(80), nullable=True)
    reference_number = Column(String(120), nullable=True)

    service_name = Column(String(120), nullable=True)
    description = Column(Text, nullable=True)

    currency = Column(String(10), nullable=False)         # BRL, USD, EUR...
    amount_original = Column(Numeric(18, 2), nullable=False)
    roe = Column(Numeric(18, 6), nullable=True)
    amount_brl = Column(Numeric(18, 2), nullable=True)

    issuance_date = Column(Date, nullable=True)
    due_date = Column(Date, nullable=True)
    status = Column(String(80), nullable=True)

    business_key = Column(String(700), nullable=False)

    operation = relationship("Operation")
    supplier = relationship("Supplier")

    __table_args__ = (
        UniqueConstraint("business_key", name="uq_entry_business_key"),
    )

def init_db():
    Base.metadata.create_all(bind=engine)

# -----------------------------
# Helpers
# -----------------------------
def s(v):
    if v is None:
        return None
    vv = str(v).strip()
    return vv if vv != "" else None

def to_decimal(v):
    if v is None:
        return None
    try:
        # aceita 1.234,56 e 1234.56
        txt = str(v).strip().replace(".", "").replace(",", ".")
        return Decimal(txt)
    except (InvalidOperation, ValueError):
        return None

def parse_voyage(voyage_code: str):
    if not voyage_code:
        return None, None
    parts = voyage_code.split("-")
    base = parts[0].strip()
    no = parts[1].strip() if len(parts) > 1 else None
    return base, no

def calc_brl(currency: str, amount_original: Decimal, roe: Decimal | None):
    if currency.upper() == "BRL":
        return amount_original
    if roe is None:
        return None
    return amount_original * roe

def get_or_create(session, model, defaults=None, **kwargs):
    obj = session.query(model).filter_by(**kwargs).first()
    if obj:
        return obj
    data = dict(kwargs)
    if defaults:
        data.update(defaults)
    obj = model(**data)
    session.add(obj)
    session.flush()
    return obj

def infer_group(supplier_type: str | None, document_type: str | None):
    dt = (document_type or "").strip().lower()
    st = (supplier_type or "").strip().upper()
    if dt in {"antec.", "antec", "pda"}:
        return "PDA"
    if st == "AGENCY" and dt in {"nd", "nfe"}:
        return "FDA"
    return "DIRECT"

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def home():
    init_db()
    return render_template("index.html")

# ---- Bases ----
@app.route("/cost-centers", methods=["GET", "POST"])
def cost_centers():
    init_db()
    session = SessionLocal()

    if request.method == "POST":
        code = s(request.form.get("code"))
        name = s(request.form.get("name"))
        cc_type = s(request.form.get("cc_type")) or "CLIENT"
        client_name = s(request.form.get("client_name"))

        if not code or not name:
            flash("Informe código e nome do CC.", "error")
            return redirect(url_for("cost_centers"))

        client = None
        if cc_type == "CLIENT" and client_name:
            client = get_or_create(session, Client, name=client_name)

        exists = session.query(CostCenter).filter_by(code=code).first()
        if exists:
            flash("CC já existe.", "error")
            session.close()
            return redirect(url_for("cost_centers"))

        cc = CostCenter(code=code, name=name, cc_type=cc_type, client_id=client.id if client else None)
        session.add(cc)
        session.commit()
        flash("CC criado com sucesso.", "ok")

    items = session.query(CostCenter).order_by(CostCenter.code.asc()).all()
    session.close()
    return render_template("cost_centers.html", items=items)

@app.route("/vessels", methods=["GET", "POST"])
def vessels():
    init_db()
    session = SessionLocal()

    if request.method == "POST":
        name = s(request.form.get("name"))
        vessel_type = s(request.form.get("vessel_type")) or "OWNED"
        charter_base = s(request.form.get("charter_base"))

        if not name:
            flash("Informe o nome do navio.", "error")
            return redirect(url_for("vessels"))

        if session.query(Vessel).filter_by(name=name).first():
            flash("Navio já existe.", "error")
            return redirect(url_for("vessels"))

        v = Vessel(name=name, vessel_type=vessel_type, charter_base=charter_base if vessel_type == "CHARTERED" else None)
        session.add(v)
        session.commit()
        flash("Navio criado.", "ok")

    items = session.query(Vessel).order_by(Vessel.name.asc()).all()
    session.close()
    return render_template("vessels.html", items=items)

@app.route("/ports", methods=["GET", "POST"])
def ports():
    init_db()
    session = SessionLocal()

    if request.method == "POST":
        name = s(request.form.get("name"))
        if not name:
            flash("Informe o nome do porto/terminal.", "error")
            return redirect(url_for("ports"))
        if session.query(Port).filter_by(name=name).first():
            flash("Porto já existe.", "error")
            return redirect(url_for("ports"))
        session.add(Port(name=name))
        session.commit()
        flash("Porto criado.", "ok")

    items = session.query(Port).order_by(Port.name.asc()).all()
    session.close()
    return render_template("ports.html", items=items)

@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():
    init_db()
    session = SessionLocal()

    if request.method == "POST":
        name = s(request.form.get("name"))
        supplier_type = s(request.form.get("supplier_type")) or "DIRECT"
        if not name:
            flash("Informe o fornecedor.", "error")
            return redirect(url_for("suppliers"))
        if session.query(Supplier).filter_by(name=name).first():
            flash("Fornecedor já existe.", "error")
            return redirect(url_for("suppliers"))
        session.add(Supplier(name=name, supplier_type=supplier_type))
        session.commit()
        flash("Fornecedor criado.", "ok")

    items = session.query(Supplier).order_by(Supplier.name.asc()).all()
    session.close()
    return render_template("suppliers.html", items=items)

# ---- Operações ----
@app.get("/operations")
def operations():
    init_db()
    session = SessionLocal()
    ops = session.query(Operation).order_by(Operation.id.desc()).limit(200).all()

    rows = []
    for op in ops:
        entries = session.query(Entry).filter(Entry.operation_id == op.id).all()
        pda = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "PDA"])
        fda = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "FDA"])
        direct = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "DIRECT"])
        rows.append({"op": op, "pda": pda, "fda": fda, "direct": direct, "diff": fda - pda})

    session.close()
    return render_template("operations.html", rows=rows)

@app.route("/operations/new", methods=["GET", "POST"])
def operation_new():
    init_db()
    session = SessionLocal()

    ccs = session.query(CostCenter).order_by(CostCenter.code.asc()).all()
    vessels = session.query(Vessel).order_by(Vessel.name.asc()).all()
    ports = session.query(Port).order_by(Port.name.asc()).all()
    agencies = session.query(Supplier).filter(Supplier.supplier_type == "AGENCY").order_by(Supplier.name.asc()).all()

    if request.method == "POST":
        cc_id = int(request.form.get("cc_id"))
        vessel_id = int(request.form.get("vessel_id"))
        port_id = int(request.form.get("port_id"))
        voyage_code = s(request.form.get("voyage_code"))
        agency_id = request.form.get("agency_id")
        agency_id = int(agency_id) if agency_id and agency_id != "0" else None

        if not voyage_code:
            flash("Informe a viagem (ex: PSV240173-20).", "error")
            session.close()
            return redirect(url_for("operation_new"))

        base, no = parse_voyage(voyage_code)

        cc = session.query(CostCenter).get(cc_id)
        v = session.query(Vessel).get(vessel_id)
        p = session.query(Port).get(port_id)

        op_key = f"{cc.code}|{v.name}|{p.name}|{voyage_code}"
        if session.query(Operation).filter_by(operation_key=op_key).first():
            flash("Operação já existe.", "error")
            session.close()
            return redirect(url_for("operations"))

        op = Operation(
            cost_center_id=cc_id,
            vessel_id=vessel_id,
            port_id=port_id,
            voyage_code=voyage_code,
            contract_base=base,
            voyage_no=no,
            agency_id=agency_id,
            operation_key=op_key
        )
        session.add(op)
        session.commit()
        flash("Operação criada.", "ok")
        session.close()
        return redirect(url_for("operation_detail", op_id=op.id))

    session.close()
    return render_template("operation_new.html", ccs=ccs, vessels=vessels, ports=ports, agencies=agencies)

@app.get("/operation/<int:op_id>")
def operation_detail(op_id):
    init_db()
    session = SessionLocal()
    op = session.query(Operation).get(op_id)
    if not op:
        session.close()
        return "Operação não encontrada", 404

    entries = session.query(Entry).filter(Entry.operation_id == op.id).order_by(Entry.id.desc()).all()
    pda = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "PDA"])
    fda = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "FDA"])
    direct = sum([float(e.amount_brl or 0) for e in entries if e.billing_group == "DIRECT"])

    session.close()
    return render_template("operation_detail.html", op=op, entries=entries, pda=pda, fda=fda, direct=direct, diff=fda - pda)

# ---- Lançamentos ----
@app.route("/operation/<int:op_id>/entry/new", methods=["GET", "POST"])
def entry_new(op_id):
    init_db()
    session = SessionLocal()
    op = session.query(Operation).get(op_id)
    if not op:
        session.close()
        return "Operação não encontrada", 404

    suppliers = session.query(Supplier).order_by(Supplier.name.asc()).all()

    if request.method == "POST":
        supplier_id = request.form.get("supplier_id")
        supplier_id = int(supplier_id) if supplier_id and supplier_id != "0" else None

        document_type = s(request.form.get("document_type"))
        po = s(request.form.get("po"))
        rqa = s(request.form.get("rqa"))
        reference_number = s(request.form.get("reference_number"))

        service_name = s(request.form.get("service_name"))
        description = s(request.form.get("description"))

        currency = (s(request.form.get("currency")) or "BRL").upper()
        amount_original = to_decimal(request.form.get("amount_original"))
        roe = to_decimal(request.form.get("roe"))
        issuance_date = s(request.form.get("issuance_date"))
        due_date = s(request.form.get("due_date"))
        status = s(request.form.get("status"))

        if amount_original is None:
            flash("Informe um valor válido.", "error")
            session.close()
            return redirect(url_for("entry_new", op_id=op_id))

        # defaults: se não escolheu fornecedor e a operação tem agência, sugere agência
        supplier = session.query(Supplier).get(supplier_id) if supplier_id else None
        if supplier is None and op.agency_id:
            supplier = session.query(Supplier).get(op.agency_id)

        supplier_type = supplier.supplier_type if supplier else None

        billing_group = infer_group(supplier_type, document_type)
        amount_brl = calc_brl(currency, amount_original, roe)

        if currency != "BRL" and amount_brl is None:
            flash("Moeda diferente de BRL exige ROE (câmbio).", "error")
            session.close()
            return redirect(url_for("entry_new", op_id=op_id))

        def parse_iso(d):
            if not d:
                return None
            try:
                y, m, dd = d.split("-")
                return date(int(y), int(m), int(dd))
            except Exception:
                return None

        iss = parse_iso(issuance_date)
        due = parse_iso(due_date)

        # evita duplicidade (BusinessKey)
        sup_name = supplier.name if supplier else ""
        bkey = f"{op.operation_key}|{billing_group}|{document_type or ''}|{po or ''}|{sup_name}|{reference_number or ''}|{currency}|{amount_original}"

        if session.query(Entry).filter_by(business_key=bkey).first():
            flash("Lançamento parecido já existe (evitando duplicidade).", "error")
            session.close()
            return redirect(url_for("operation_detail", op_id=op_id))

        e = Entry(
            operation_id=op.id,
            supplier_id=supplier.id if supplier else None,
            billing_group=billing_group,
            document_type=document_type,
            po=po,
            rqa=rqa,
            reference_number=reference_number,
            service_name=service_name,
            description=description,
            currency=currency,
            amount_original=amount_original,
            roe=roe,
            amount_brl=amount_brl,
            issuance_date=iss,
            due_date=due,
            status=status,
            business_key=bkey
        )
        session.add(e)
        session.commit()
        flash("Despesa lançada.", "ok")
        session.close()
        return redirect(url_for("operation_detail", op_id=op_id))

    session.close()
    return render_template("entry_new.html", op=op, suppliers=suppliers)

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
