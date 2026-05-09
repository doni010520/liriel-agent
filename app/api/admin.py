"""
Admin API routes for event management and admin panel.
"""

from datetime import date, datetime

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from loguru import logger

from app.services.events_service import (
    add_event,
    remove_event,
    list_future_events,
)

router = APIRouter(prefix="/admin", tags=["admin-panel"])


# ── Schemas ────────────────────────────────────────────────

class EventCreate(BaseModel):
    name: str
    event_date: str  # DD/MM/YYYY
    start_time: str = ""
    end_time: str = ""
    location: str = ""
    description: str = ""


class EventDelete(BaseModel):
    name: str


# ── API Endpoints ──────────────────────────────────────────

@router.get("/events", response_model=list)
async def api_list_events():
    return await list_future_events(days_ahead=365)


@router.post("/events")
async def api_add_event(event: EventCreate):
    try:
        event_date = datetime.strptime(event.event_date, "%d/%m/%Y").date()
    except ValueError:
        raise HTTPException(400, "Data inválida. Use DD/MM/YYYY.")

    result = await add_event(
        name=event.name,
        event_date=event_date,
        start_time=event.start_time,
        end_time=event.end_time,
        location=event.location,
        description=event.description,
        created_by="admin-panel",
    )
    if result:
        return {"success": True, "message": f"Evento '{event.name}' criado"}
    raise HTTPException(500, "Erro ao criar evento")


@router.delete("/events")
async def api_delete_event(event: EventDelete):
    success = await remove_event(event.name)
    if success:
        return {"success": True, "message": f"Evento '{event.name}' removido"}
    raise HTTPException(404, f"Evento '{event.name}' não encontrado")


# ── Admin Panel HTML ───────────────────────────────────────

@router.get("/panel", response_class=HTMLResponse)
async def admin_panel():
    """Serve the admin panel as a single HTML page."""
    return ADMIN_HTML


ADMIN_HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Liriel Admin — Eventos</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f0f2f5; color: #1a1a2e; }
  
  .header { background: #1a5276; color: white; padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  .header h1 { font-size: 1.3em; font-weight: 600; }
  
  .container { max-width: 800px; margin: 24px auto; padding: 0 16px; }
  
  .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .card h2 { font-size: 1.1em; margin-bottom: 16px; color: #1a5276; }
  
  .form-row { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; }
  .form-row input { flex: 1; min-width: 140px; padding: 10px 12px; border: 1px solid #ddd; border-radius: 8px; font-size: 0.95em; }
  .form-row input:focus { outline: none; border-color: #2e86c1; }
  
  .btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 0.95em; cursor: pointer; font-weight: 500; }
  .btn-primary { background: #2e86c1; color: white; }
  .btn-primary:hover { background: #1a5276; }
  .btn-danger { background: #e74c3c; color: white; padding: 6px 12px; font-size: 0.85em; }
  .btn-danger:hover { background: #c0392b; }
  
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 10px 8px; border-bottom: 2px solid #eee; font-size: 0.85em; color: #666; text-transform: uppercase; }
  td { padding: 12px 8px; border-bottom: 1px solid #f0f0f0; font-size: 0.95em; }
  tr:hover { background: #f8f9fa; }
  
  .empty { text-align: center; padding: 40px; color: #999; }
  .toast { position: fixed; bottom: 24px; right: 24px; background: #27ae60; color: white; padding: 12px 20px; border-radius: 8px; display: none; font-size: 0.95em; z-index: 100; }
  .toast.error { background: #e74c3c; }
  .toast.show { display: block; }
</style>
</head>
<body>

<div class="header">
  <span style="font-size:1.5em">🌸</span>
  <h1>Liriel Admin — Eventos</h1>
</div>

<div class="container">
  <div class="card">
    <h2>Adicionar Evento</h2>
    <div class="form-row">
      <input type="text" id="name" placeholder="Nome do evento" />
      <input type="text" id="date" placeholder="DD/MM/YYYY" />
    </div>
    <div class="form-row">
      <input type="text" id="start" placeholder="Início (ex: 9h)" />
      <input type="text" id="end" placeholder="Fim (ex: 17h)" />
      <input type="text" id="location" placeholder="Local" />
    </div>
    <div class="form-row">
      <input type="text" id="description" placeholder="Descrição (opcional)" style="flex:3" />
      <button class="btn btn-primary" onclick="addEvent()">Adicionar</button>
    </div>
  </div>

  <div class="card">
    <h2>Eventos Cadastrados</h2>
    <div id="events-table"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const API = '/admin';

async function loadEvents() {
  try {
    const res = await fetch(API + '/events');
    const events = await res.json();
    const container = document.getElementById('events-table');
    
    if (!events.length) {
      container.innerHTML = '<div class="empty">Nenhum evento cadastrado</div>';
      return;
    }
    
    let html = '<table><thead><tr><th>Evento</th><th>Data</th><th>Horário</th><th>Local</th><th></th></tr></thead><tbody>';
    events.forEach(e => {
      const time = e.start_time ? (e.end_time ? e.start_time + ' - ' + e.end_time : e.start_time) : '-';
      html += '<tr>';
      html += '<td><strong>' + e.name + '</strong>' + (e.description ? '<br><small style="color:#666">' + e.description + '</small>' : '') + '</td>';
      html += '<td>' + e.date + '</td>';
      html += '<td>' + time + '</td>';
      html += '<td>' + (e.location || '-') + '</td>';
      html += '<td><button class="btn btn-danger" onclick="deleteEvent(\\'' + e.name.replace(/'/g, "\\\\'") + '\\')">Remover</button></td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (err) {
    console.error(err);
  }
}

async function addEvent() {
  const data = {
    name: document.getElementById('name').value,
    event_date: document.getElementById('date').value,
    start_time: document.getElementById('start').value,
    end_time: document.getElementById('end').value,
    location: document.getElementById('location').value,
    description: document.getElementById('description').value,
  };
  
  if (!data.name || !data.event_date) {
    showToast('Preencha nome e data', true);
    return;
  }
  
  try {
    const res = await fetch(API + '/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (res.ok) {
      showToast('Evento adicionado!');
      document.querySelectorAll('.form-row input').forEach(i => i.value = '');
      loadEvents();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Erro', true);
    }
  } catch (err) {
    showToast('Erro de conexão', true);
  }
}

async function deleteEvent(name) {
  if (!confirm('Remover "' + name + '"?')) return;
  try {
    const res = await fetch(API + '/events', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (res.ok) {
      showToast('Evento removido!');
      loadEvents();
    }
  } catch (err) {
    showToast('Erro', true);
  }
}

function showToast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 3000);
}

loadEvents();
</script>
</body>
</html>
"""
