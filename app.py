import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash, Response
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime, Numeric, ForeignKey, UniqueConstraint, Text, or_
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

import qive

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

class QiveNote(Base):
    """Nota (NF-e / CT-e) baixada do Qive pelo robô."""
    __tablename__ = "qive_notes"
    id = Column(Integer, primary_key=True)
    access_key = Column(String(44), unique=True, nullable=False)
    doc_type = Column(String(5), nullable=False)          # NFE | CTE
    number = Column(String(20), nullable=True)
    series = Column(String(5), nullable=True)
    issue_date = Column(Date, nullable=True)
    issuer_cnpj = Column(String(14), nullable=True)
    issuer_name = Column(String(200), nullable=True)
    recipient_cnpj = Column(String(14), nullable=True)
    recipient_name = Column(String(200), nullable=True)
    total_value = Column(Numeric(18, 2), nullable=True)
    summary = Column(String(500), nullable=True)
    xml = Column(Text, nullable=False)
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)

class QiveSyncState(Base):
    """Posição (cursor) do robô em cada endpoint do Qive."""
    __tablename__ = "qive_sync_state"
    id = Column(Integer, primary_key=True)
    doc_type = Column(String(5), unique=True, nullable=False)
    cursor = Column(String(40), nullable=True)
    last_run = Column(DateTime, nullable=True)
    last_count = Column(Integer, nullable=True)
    last_error = Column(String(500), nullable=True)

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
# Robô Qive
# -----------------------------
def upsert_qive_notes(session, items):
    """Grava/atualiza notas (lista de (access_key, xml)). Retorna quantas foram gravadas."""
    n = 0
    for key, xml_str in items:
        data = qive.parse_xml(key, xml_str)
        note = session.query(QiveNote).filter_by(access_key=key).first()
        if note is None:
            note = QiveNote(access_key=key)
            session.add(note)
        for k, v in data.items():
            setattr(note, k, v)
        note.xml = xml_str
        note.fetched_at = datetime.utcnow()
        n += 1
    session.flush()
    return n

def run_qive_robot(max_pages=4):
    """
    Busca as notas novas no Qive a partir do último cursor salvo.
    max_pages limita o volume por execução (cada página = até 50 notas),
    para não estourar o timeout do servidor web quando disparado pelo botão.
    """
    session = SessionLocal()
    report = {}
    try:
        for doc_type in qive.ENDPOINTS:
            state = get_or_create(session, QiveSyncState, doc_type=doc_type)
            total = 0
            try:
                for _ in range(max_pages):
                    items, next_cursor = qive.fetch_page(doc_type, state.cursor)
                    total += upsert_qive_notes(session, items)
                    state.cursor = next_cursor
                    session.commit()  # salva progresso página a página
                    if len(items) < qive.PAGE_LIMIT:
                        break
                state.last_error = None
            except qive.QiveError as e:
                session.rollback()
                state = get_or_create(session, QiveSyncState, doc_type=doc_type)
                state.last_error = str(e)[:500]
            state.last_run = datetime.utcnow()
            state.last_count = total
            session.commit()
            report[doc_type] = {"count": total, "error": state.last_error}
    finally:
        session.close()
    return report

@app.cli.command("qive-sync")
def qive_sync_cli():
    """Roda o robô Qive (uso em cron: flask --app app qive-sync)."""
    init_db()
    report = run_qive_robot(max_pages=int(os.getenv("QIVE_MAX_PAGES", "40")))
    for doc_type, r in report.items():
        print(f"{doc_type}: {r['count']} nota(s)" + (f" | ERRO: {r['error']}" if r["error"] else ""))

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

# ---- Workbench ----
@app.get("/workbench")
def workbench():
    init_db()
    return render_template("workbench.html")

@app.get("/workbench/qive")
def workbench_qive():
    init_db()
    session = SessionLocal()

    f = {k: s(request.args.get(k)) for k in
         ["q", "key", "cnpj", "number", "doc_type", "date_from", "date_to", "value_min", "value_max"]}

    query = session.query(QiveNote)
    searched = any(f.values())

    if f["key"]:
        query = query.filter(QiveNote.access_key.contains(qive.clean_key(f["key"])))
    if f["q"]:
        like = f"%{f['q']}%"
        query = query.filter(or_(QiveNote.issuer_name.ilike(like),
                                 QiveNote.recipient_name.ilike(like),
                                 QiveNote.summary.ilike(like)))
    if f["cnpj"]:
        cnpj = qive.clean_key(f["cnpj"])
        query = query.filter(or_(QiveNote.issuer_cnpj.contains(cnpj),
                                 QiveNote.recipient_cnpj.contains(cnpj)))
    if f["number"]:
        query = query.filter(QiveNote.number == f["number"].lstrip("0"))
    if f["doc_type"] in ("NFE", "CTE"):
        query = query.filter(QiveNote.doc_type == f["doc_type"])
    try:
        if f["date_from"]:
            query = query.filter(QiveNote.issue_date >= date.fromisoformat(f["date_from"]))
        if f["date_to"]:
            query = query.filter(QiveNote.issue_date <= date.fromisoformat(f["date_to"]))
    except ValueError:
        flash("Data inválida no filtro.", "error")
    vmin, vmax = to_decimal(f["value_min"]), to_decimal(f["value_max"])
    if vmin is not None:
        query = query.filter(QiveNote.total_value >= vmin)
    if vmax is not None:
        query = query.filter(QiveNote.total_value <= vmax)

    notes = query.order_by(QiveNote.issue_date.desc().nullslast(), QiveNote.id.desc()).limit(300).all()
    total_db = session.query(QiveNote).count()
    states = session.query(QiveSyncState).order_by(QiveSyncState.doc_type).all()
    session.close()

    return render_template("workbench_qive.html", notes=notes, f=f, searched=searched,
                           total_db=total_db, states=states, configured=qive.is_configured())

@app.post("/workbench/qive/sync")
def workbench_qive_sync():
    init_db()
    report = run_qive_robot(max_pages=4)
    for doc_type, r in report.items():
        if r["error"]:
            flash(f"Robô {doc_type}: erro - {r['error']}", "error")
        else:
            flash(f"Robô {doc_type}: {r['count']} nota(s) atualizada(s).", "ok")
    return redirect(url_for("workbench_qive"))

@app.post("/workbench/qive/lookup")
def workbench_qive_lookup():
    """Consulta direta no Qive por chave de acesso (uma por linha), mesmo que o robô ainda não tenha baixado."""
    init_db()
    keys = [qive.clean_key(k) for k in (request.form.get("keys") or "").splitlines()]
    keys = list(dict.fromkeys(k for k in keys if len(k) == 44))
    if not keys:
        flash("Informe ao menos uma chave de acesso válida (44 dígitos).", "error")
        return redirect(url_for("workbench_qive"))

    session = SessionLocal()
    found = 0
    try:
        for doc_type in qive.ENDPOINTS:
            group = [k for k in keys if qive.doc_type_from_key(k) == doc_type]
            for i in range(0, len(group), qive.PAGE_LIMIT):
                found += upsert_qive_notes(session, qive.fetch_by_keys(doc_type, group[i:i + qive.PAGE_LIMIT]))
        session.commit()
    except qive.QiveError as e:
        session.rollback()
        flash(f"Erro ao consultar o Qive: {e}", "error")
        session.close()
        return redirect(url_for("workbench_qive"))
    session.close()

    missing = len(keys) - found
    flash(f"{found} nota(s) encontrada(s) no Qive." + (f" {missing} não encontrada(s)." if missing else ""),
          "ok" if not missing else "error")
    if len(keys) == 1 and found:
        return redirect(url_for("workbench_qive_detail", access_key=keys[0]))
    return redirect(url_for("workbench_qive", key="\n".join(keys) if len(keys) == 1 else None))

@app.get("/workbench/qive/<access_key>")
def workbench_qive_detail(access_key):
    init_db()
    session = SessionLocal()
    note = session.query(QiveNote).filter_by(access_key=access_key).first()
    if not note:
        session.close()
        return "Nota não encontrada", 404

    # lançamentos do sistema que citam esta nota (nº ou chave no campo referência)
    refs = [note.access_key] + ([note.number] if note.number else [])
    entries = session.query(Entry).filter(Entry.reference_number.in_(refs)).all()
    for e in entries:
        _ = e.operation.operation_key  # carrega antes de fechar a sessão
    session.close()
    return render_template("workbench_qive_detail.html", note=note, entries=entries)

@app.get("/workbench/qive/<access_key>/xml")
def workbench_qive_xml(access_key):
    init_db()
    session = SessionLocal()
    note = session.query(QiveNote).filter_by(access_key=access_key).first()
    session.close()
    if not note:
        return "Nota não encontrada", 404
    return Response(note.xml, mimetype="application/xml",
                    headers={"Content-Disposition": f"attachment; filename={note.doc_type}-{access_key}.xml"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
