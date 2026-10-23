import os
import sqlite3
import platform
import socket
import subprocess
import csv
import io
import json
from datetime import datetime
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import streamlit as st
import pandas as pd

from coletor import coletar_inventario as local_diagnostics, TOKEN_COLETA, PORTA

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "dados"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "office_telco_ti.db"

st.set_page_config(page_title="Office Telco | Painel de TI", page_icon="🖥", layout="wide")

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute('''
            CREATE TABLE IF NOT EXISTS inventario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coletado_em TEXT NOT NULL,
                hostname TEXT NOT NULL,
                usuario TEXT,
                sistema TEXT,
                versao TEXT,
                processador TEXT,
                memoria_gb REAL,
                memoria_tipo TEXT,
                disco_tipo TEXT,
                disco_tamanho_gb REAL,
                disco_livre_gb REAL,
                ipv4 TEXT,
                origem TEXT NOT NULL DEFAULT 'Coleta local',
                pa TEXT,
                anydesk TEXT,
                matricula TEXT
            )
        ''')
        cols = [r['name'] for r in con.execute("PRAGMA table_info(inventario)").fetchall()]
        if "memoria_tipo" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN memoria_tipo TEXT")
        if "disco_tipo" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN disco_tipo TEXT")
        if "disco_tamanho_gb" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN disco_tamanho_gb REAL")
        if "pa" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN pa TEXT")
        if "anydesk" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN anydesk TEXT")
        if "matricula" not in cols:
            con.execute("ALTER TABLE inventario ADD COLUMN matricula TEXT")

def reordenar_ids_inventario():
    with db() as con:
        rows = con.execute("SELECT * FROM inventario ORDER BY id ASC").fetchall()
        con.execute("DELETE FROM inventario")
        con.execute("DELETE FROM sqlite_sequence WHERE name='inventario'")
        novo_id = 1
        for r in rows:
            con.execute('''
                INSERT INTO inventario (id, coletado_em, hostname, usuario, sistema, versao, processador, memoria_gb, memoria_tipo, disco_tipo, disco_tamanho_gb, disco_livre_gb, ipv4, origem, pa, anydesk, matricula)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                novo_id, r["coletado_em"], r["hostname"], r["usuario"], r["sistema"],
                r["versao"], r["processador"], r["memoria_gb"], r["memoria_tipo"] if "memoria_tipo" in r.keys() else None,
                r["disco_tipo"] if "disco_tipo" in r.keys() else None, r["disco_tamanho_gb"] if "disco_tamanho_gb" in r.keys() else None, r["disco_livre_gb"],
                r["ipv4"], r["origem"], r.get("pa"), r.get("anydesk"), r.get("matricula")
            ))
            novo_id += 1
        con.commit()

DB_LOCK = threading.Lock()
CAMPOS_TEXTO = ["hostname", "usuario", "sistema", "versao", "processador", "memoria_tipo", "disco_tipo", "ipv4", "origem", "pa", "anydesk", "matricula"]
CAMPOS_NUM = ["memoria_gb", "disco_tamanho_gb", "disco_livre_gb"]

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def salvar_inventario(info):
    registro = {c: (str(info.get(c))[:200] if info.get(c) is not None else None) for c in CAMPOS_TEXTO}
    for c in CAMPOS_NUM:
        registro[c] = _num(info.get(c))
    registro["coletado_em"] = str(info.get("coletado_em") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))[:30]
    registro["origem"] = registro["origem"] or "Coleta local"
    with DB_LOCK:
        with db() as con:
            con.execute('''
                INSERT INTO inventario (coletado_em, hostname, usuario, sistema, versao, processador, memoria_gb, memoria_tipo, disco_tipo, disco_tamanho_gb, disco_livre_gb, ipv4, origem, pa, anydesk, matricula)
                VALUES (:coletado_em, :hostname, :usuario, :sistema, :versao, :processador, :memoria_gb, :memoria_tipo, :disco_tipo, :disco_tamanho_gb, :disco_livre_gb, :ipv4, :origem, :pa, :anydesk, :matricula)
            ''', registro)
        reordenar_ids_inventario()

class Receptor(BaseHTTPRequestHandler):
    def _responder(self, codigo, corpo):
        dados = json.dumps(corpo).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)

    def do_POST(self):
        if self.path != "/inventario":
            return self._responder(404, {"ok": False})
        if self.headers.get("X-Token") != TOKEN_COLETA:
            return self._responder(403, {"ok": False, "erro": "token invalido"})
        try:
            tamanho = int(self.headers.get("Content-Length", 0))
            if tamanho <= 0 or tamanho > 30000:
                raise ValueError("tamanho invalido")
            info = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            if not isinstance(info, dict) or not info.get("hostname"):
                raise ValueError("dados invalidos")
            info["origem"] = f"Coleta remota ({self.client_address[0]})"
            salvar_inventario(info)
            self._responder(200, {"ok": True})
        except Exception as exc:
            self._responder(400, {"ok": False, "erro": str(exc)})

    def log_message(self, *args):
        pass

@st.cache_resource
def iniciar_receptor():
    try:
        servidor = ThreadingHTTPServer(("0.0.0.0", PORTA), Receptor)
    except OSError:
        return False
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    return True

init_db()
receptor_ativo = iniciar_receptor()

st.markdown('''
    <style>
    .stApp { background: linear-gradient(135deg, #071321 0%, #0b1d31 55%, #08111e 100%); }
    [data-testid="stSidebar"] { background: #081525; border-right: 1px solid #183b5b; }
    h1, h2, h3, p, label { color: #eaf4ff; }
    .hero { padding: 1.5rem 1.7rem; border: 1px solid #147ac0; border-radius: 18px;
            background: linear-gradient(115deg, rgba(0,100,210,.28), rgba(0,210,190,.08)); margin-bottom: 1.2rem; }
    .hero-kicker { color: #55c7ff; letter-spacing: .14em; font-size: .78rem; font-weight: 700; }
    .hero h1 { margin: .4rem 0; color: #f4f9ff; font-size: 2.35rem; }
    .hero p { color: #c4d8ec; max-width: 800px; }
    div[data-testid="stMetric"] { background: rgba(15,45,72,.7); border: 1px solid #1b5078; padding: 14px; border-radius: 12px; }
    div.stButton > button[kind="primary"] { background: #087ed0; border: 1px solid #20b8ff; border-radius: 9px; }
    </style>
''', unsafe_allow_html=True)

st.title("🛠️ Office Telco | Painel Central de TI — Ryan")

SENHA_ADMIN = "ryan123"

with st.sidebar:
    st.header("Controlo de Acesso")
    tipo_usuario = st.radio("Perfil de Acesso", ["Colaborador (Apenas Inventariar)", "Administrador (Painel Completo)"])
    
    autenticado = True
    if tipo_usuario == "Administrador (Painel Completo)":
        senha_dig = st.text_input("Palavra-passe Admin", type="password")
        if senha_dig != SENHA_ADMIN:
            autenticado = False
            st.warning("Insira a palavra-passe correta para aceder às funções de administrador.")

    st.divider()
    if autenticado and tipo_usuario == "Administrador (Painel Completo)":
        st.header("Navegação")
        page = st.radio("Escolha um módulo", ["Visão geral", "Inventário", "Active Directory", "Configuração e segurança"])
    else:
        page = "Modo Colaborador"
    st.divider()
    st.caption("Faça backup periódico da pasta dados/.")

SCRIPT_COLETA_PS = r'''
$ErrorActionPreference = 'SilentlyContinue'
$servidor = '__SERVIDOR__'
$porta = __PORTA__
$token = '__TOKEN__'
Write-Host '=========================================='
Write-Host '   OFFICE TELCO - COLETA DE INVENTARIO'
Write-Host '=========================================='
Write-Host ''
$paInput = Read-Host 'Digite a sua P.A. (opcional, Pressione Enter para ignorar,Exemplo: PA-P01)'
$anydeskInput = Read-Host 'Digite o seu AnyDesk (opcional, Pressione Enter para ignorar)'
$matInput = Read-Host 'Digite a sua Matricula (opcional, Pressione Enter para ignorar)'

Write-Host ''
Write-Host 'Coletando dados técnicos deste computador...'
$os = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-CimInstance Win32_Processor | Select-Object -First 1).Name.Trim()
$cs = Get-CimInstance Win32_ComputerSystem
$mem = Get-CimInstance Win32_PhysicalMemory | Select-Object -First 1
$disk = Get-CimInstance Win32_DiskDrive | Select-Object -First 1
$ramTipo = switch ($mem.SMBIOSMemoryType) { 20 {'DDR'} 21 {'DDR2'} 24 {'DDR3'} 26 {'DDR4'} 34 {'DDR5'} default {'Nao identificado'} }
$pd = Get-PhysicalDisk | Select-Object -First 1
if ($pd -and $pd.MediaType) { $dTipo = [string]$pd.MediaType } elseif ($disk.Model -match 'SSD|NVMe') { $dTipo = 'SSD' } else { $dTipo = 'HDD (HD)' }
$ld = Get-CimInstance Win32_LogicalDisk -Filter ("DeviceID='" + $env:SystemDrive + "'")
$cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1
$ip = $cfg.IPv4Address.IPAddress
if (-not $ip) { $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1).IPAddress }

$info = [ordered]@{
  coletado_em = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
  hostname = $env:COMPUTERNAME
  usuario = $env:USERNAME
  sistema = $os.Caption
  versao = ('{0} (compilacao {1})' -f $os.Version, $os.BuildNumber)
  processador = $cpu
  memoria_gb = [math]::Round($cs.TotalPhysicalMemory / 1GB, 2)
  memoria_tipo = $ramTipo
  disco_tipo = $dTipo
  disco_tamanho_gb = [math]::Round($disk.Size / 1GB, 2)
  disco_livre_gb = [math]::Round($ld.FreeSpace / 1GB, 2)
  ipv4 = $ip
  origem = 'Coleta remota'
  pa = $paInput
  anydesk = $anydeskInput
  matricula = $matInput
}
$json = $info | ConvertTo-Json
$arq = Join-Path ([Environment]::GetFolderPath('Desktop')) ('inventario_' + $env:COMPUTERNAME + '.json')
[IO.File]::WriteAllText($arq, $json, (New-Object Text.UTF8Encoding $false))

try {
  Invoke-RestMethod -Uri ('http://' + $servidor + ':' + $porta + '/inventario') -Method Post -Body ([Text.Encoding]::UTF8.GetBytes($json)) -ContentType 'application/json' -Headers @{ 'X-Token' = $token } -TimeoutSec 15 -ErrorAction Stop | Out-Null
  Write-Host ''
  Write-Host 'PRONTO! Inventario enviado automaticamente com sucesso!' -ForegroundColor Green
} catch {
  Write-Host ''
  Write-Host 'Envio automatico bloqueado pela rede/nuvem, mas arquivo gerado com sucesso!' -ForegroundColor Yellow
  Write-Host ('Arquivo salvo na Area de Trabalho: ' + $arq)
  Write-Host 'Por favor, envie este arquivo na aba do site da TI.'
}
'''

def gerar_bat_coleta(servidor):
    ps = (SCRIPT_COLETA_PS.replace("__SERVIDOR__", servidor)
          .replace("__PORTA__", str(PORTA)).replace("__TOKEN__", TOKEN_COLETA))
    bat = (
        "@echo off\n"
        "title Office Telco - Enviar inventario\n"
        "powershell -NoProfile -ExecutionPolicy Bypass -Command "
        "\"$s = Get-Content -LiteralPath '%~f0' -Raw; $i = $s.IndexOf('#'+'PS_START'); iex $s.Substring($i + 9)\"\n"
        "echo.\n"
        "pause\n"
        "exit /b\n"
        "#PS_START\n" + ps
    )
    return bat.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii", "replace")

def endereco_do_painel():
    try:
        host = st.context.headers.get("Host", "")
        host = host.rsplit(":", 1)[0] if host else ""
        if host and host not in ("localhost", "127.0.0.1"):
            return host
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostname()

if page == "Modo Colaborador":
    st.subheader("Envio de Inventário do Computador")
    st.write("**1.** Clique no botão abaixo para baixar o arquivo de envio. **2.** Dê duplo clique nele: uma janela preta vai pedir opcionalmente a sua **P.A.**, **AnyDesk** e **Matrícula**. **3.** Pronto!")
    st.download_button(
        "⬇️ Baixar e enviar o inventário do meu computador",
        data=gerar_bat_coleta(endereco_do_painel()),
        file_name="Enviar_Inventario.bat",
        mime="application/octet-stream",
        type="primary",
    )
    st.caption("O Windows ou navegador pode avisar que o arquivo é desconhecido: escolha manter/executar mesmo assim.")

    with st.expander("O envio automático não funcionou? (Enviar arquivo manual)"):
        st.write("O arquivo `.bat` também cria um ficheiro `inventario_*.json` na sua Área de Trabalho caso a rede bloqueie. Pode enviá-lo aqui:")
        arq = st.file_uploader("Arquivo inventario_*.json", type=["json"])
        if arq is not None and st.button("Enviar arquivo para a TI"):
            try:
                dados = json.loads(arq.getvalue().decode("utf-8-sig"))
                if not isinstance(dados, dict) or not dados.get("hostname"):
                    raise ValueError("arquivo invalido")
                dados["origem"] = "Coleta remota (arquivo)"
                salvar_inventario(dados)
                st.success("Inventário enviado com sucesso para a TI. Obrigado!")
            except Exception:
                st.error("Arquivo inválido. Use o ficheiro gerado pelo Enviar_Inventario.bat.")

elif page == "Visão geral":
    st.markdown('''
    <div class="hero">
      <div class="hero-kicker">OFFICE TELCO · SUPORTE DE TI</div>
      <h1>Olá, Ryan! 👋</h1>
      <p>Bem-vindo ao seu painel de TI. Consulte as informações deste computador,
      gerencie equipamentos no inventário centralizado e verifique o Active Directory.</p>
    </div>
    ''', unsafe_allow_html=True)

    with db() as con:
        invent = con.execute("SELECT COUNT(DISTINCT hostname) FROM inventario").fetchone()[0]
        total_maquinas = con.execute("SELECT COUNT(*) FROM inventario").fetchone()[0]
    
    c1, c2 = st.columns(2)
    c1.metric("Computadores no Inventário", total_maquinas)
    c2.metric("Maquinas Únicas (Hostnames)", invent)

    st.subheader("Diagnóstico do servidor")
    if st.button("Executar e salvar diagnóstico local", type="primary"):
        info = local_diagnostics()
        info["origem"] = "Servidor do painel"
        info["pa"] = st.text_input("P.A. (Opcional)", value="")
        info["anydesk"] = st.text_input("AnyDesk (Opcional)", value="")
        info["matricula"] = st.text_input("Matrícula (Opcional)", value="")
        salvar_inventario(info)
        st.success("Informações atualizadas e salvas no inventário.")

elif page == "Inventário":
    st.subheader("Inventário Geral Centralizado")
    
    if "edit_id" not in st.session_state:
        st.session_state["edit_id"] = None

    with db() as con:
        rows = con.execute("SELECT * FROM inventario ORDER BY id ASC").fetchall()
        
    records = [dict(r) for r in rows]

    if records:
        df = pd.DataFrame(records)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button("Exportar inventário para CSV", df.to_csv(index=False, sep=";").encode("utf-8-sig"), "inventario_office_telco.csv", "text/csv")

        st.markdown("### 🛠️ Gerenciar Registro (Editar / Excluir)")
        
        item_options = {f"ID {r['id']} | Host: {r['hostname']} | Matrícula: {r.get('matricula') or 'N/A'} | P.A.: {r.get('pa') or 'N/A'}": r['id'] for r in records}
        selected_label = st.selectbox("Selecione um registro:", list(item_options.keys()))
        selected_id = item_options[selected_label]

        col_btn_edit, col_btn_del = st.columns(2)
        with col_btn_edit:
            if st.button("✏️ Editar Registro Selecionado"):
                st.session_state["edit_id"] = selected_id

        with col_btn_del:
            if st.button("🗑️ Excluir Registro Selecionado", type="primary"):
                with db() as con:
                    con.execute("DELETE FROM inventario WHERE id = ?", (selected_id,))
                    con.commit()
                reordenar_ids_inventario()
                st.success(f"Registro removido e IDs reordenados com sucesso!")
                if st.session_state["edit_id"] == selected_id:
                    st.session_state["edit_id"] = None
                st.rerun()

        if st.session_state["edit_id"] is not None:
            item_to_edit = next((r for r in records if r["id"] == st.session_state["edit_id"]), None)
            if item_to_edit:
                st.markdown(f"#### ✏️ Editando Registro ID {item_to_edit['id']}")
                with st.form("form_editar"):
                    e_hostname = st.text_input("Hostname", value=item_to_edit["hostname"] or "")
                    e_usuario = st.text_input("Usuário", value=item_to_edit["usuario"] or "")
                    
                    c_info1, c_info2, c_info3 = st.columns(3)
                    with c_info1:
                        e_matricula = st.text_input("Matrícula", value=item_to_edit.get("matricula") or "")
                    with c_info2:
                        e_pa = st.text_input("P.A.", value=item_to_edit.get("pa") or "")
                    with c_info3:
                        e_anydesk = st.text_input("AnyDesk", value=item_to_edit.get("anydesk") or "")

                    e_sistema = st.text_input("Sistema Operacional", value=item_to_edit["sistema"] or "")
                    e_versao = st.text_input("Versão", value=item_to_edit["versao"] or "")
                    e_processador = st.text_input("Processador", value=item_to_edit["processador"] or "")
                    
                    c_mem1, c_mem2 = st.columns(2)
                    with c_mem1:
                        e_memoria = st.number_input("Memória Total (GB)", value=float(item_to_edit["memoria_gb"] or 0.0), step=0.1)
                    with c_mem2:
                        e_memoria_tipo = st.text_input("Tipo de RAM", value=item_to_edit.get("memoria_tipo") or "")

                    c_disk1, c_disk2, c_disk3 = st.columns(3)
                    with c_disk1:
                        e_disco_tipo = st.text_input("Tipo de Disco", value=item_to_edit.get("disco_tipo") or "")
                    with c_disk2:
                        e_disco_tamanho = st.number_input("Tamanho Total do Disco (GB)", value=float(item_to_edit.get("disco_tamanho_gb") or 0.0), step=0.1)
                    with c_disk3:
                        e_disco_livre = st.number_input("Disco Livre (GB)", value=float(item_to_edit["disco_livre_gb"] or 0.0), step=0.1)

                    e_ipv4 = st.text_input("IPv4", value=item_to_edit["ipv4"] or "")
                    e_origem = st.text_input("Origem", value=item_to_edit["origem"] or "Coleta local")

                    col_salvar, col_cancelar = st.columns(2)
                    with col_salvar:
                        submitted = st.form_submit_button("Salvar Alterações")
                    with col_cancelar:
                        canceled = st.form_submit_button("Cancelar")

                    if submitted:
                        with db() as con:
                            con.execute('''
                                UPDATE inventario
                                SET hostname = ?, usuario = ?, sistema = ?, versao = ?, processador = ?, 
                                    memoria_gb = ?, memoria_tipo = ?, disco_tipo = ?, disco_tamanho_gb = ?, disco_livre_gb = ?, 
                                    ipv4 = ?, origem = ?, pa = ?, anydesk = ?, matricula = ?
                                WHERE id = ?
                            ''', (e_hostname, e_usuario, e_sistema, e_versao, e_processador, 
                                  e_memoria, e_memoria_tipo, e_disco_tipo, e_disco_tamanho, e_disco_livre, 
                                  e_ipv4, e_origem, e_pa, e_anydesk, e_matricula, item_to_edit['id']))
                        st.success("Registro atualizado com sucesso!")
                        st.session_state["edit_id"] = None
                        st.rerun()

                    if canceled:
                        st.session_state["edit_id"] = None
                        st.rerun()

    else:
        st.info("Nenhum registro de inventário centralizado ainda.")

elif page == "Active Directory":
    st.subheader("Active Directory — consulta somente leitura")
    st.write("A consulta abaixo tenta ler o domínio, a quantidade de usuários e a quantidade de computadores.")
    if st.button("Testar conexão e consultar resumo do AD", type="primary"):
        data, error = run_readonly_ad_query()
        if data:
            st.success("Consulta concluída.")
            st.json(data)
        else:
            st.error(error)

elif page == "Configuração e segurança":
    st.subheader("Estado e cuidados")
    st.markdown('''
- O inventário centralizado é armazenado em `dados/office_telco_ti.db`.
- Faça backup periódico da pasta `dados/`.
''')
    st.json({"hostname": socket.gethostname(), "Windows": platform.platform(), "Python": platform.python_version()})
