# realtime_utils.py
"""
Utilitários para sincronização em tempo real e cache inteligente.
Implementa auto-refresh e detecção de mudanças para multi-usuário.
"""

import streamlit as st
from utils import safe_get_all_records
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import hashlib
import json

class RealtimeSync:
    """Gerencia sincronização em tempo real entre usuários."""
    
    # Configurações de refresh
    REFRESH_INTERVAL_MS = 5000  # 5 segundos
    CACHE_TTL_SECONDS = 30      # Cache curto para dados mutáveis
    
    # Aba de metadados no Google Sheets
    METADATA_TAB_NAME = "Sync_Metadata"
    
    def __init__(self, gspread_client, sheet_name: str = "UAEW_App"):
        self.gc = gspread_client
        self.sheet_name = sheet_name
        self._ensure_metadata_tab()
    
    def _ensure_metadata_tab(self):
        """Cria aba 'Sync_Metadata' se não existir."""
        try:
            spreadsheet = self.gc.open(self.sheet_name)
            try:
                self.metadata_ws = spreadsheet.worksheet(self.METADATA_TAB_NAME)
            except Exception:
                # Cria aba se não existir
                self.metadata_ws = spreadsheet.add_worksheet(
                    title=self.METADATA_TAB_NAME,
                    rows=100,
                    cols=4
                )
                # Header
                self.metadata_ws.append_row([
                    "Tab Name", "Last Modified", "Modified By", "Change Hash"
                ])
        except Exception as e:
            st.warning(f"Erro ao inicializar sync metadata: {e}", icon="⚠️")
    
    def record_change(self, tab_name: str, user_id: str, data_hash: Optional[str] = None):
        """
        Registra mudança em uma aba.
        
        Args:
            tab_name: Nome da aba modificada
            user_id: ID do usuário que fez a mudança
            data_hash: Hash opcional dos dados (para detecção de mudanças)
        """
        try:
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            
            # Busca registro existente
            all_records = safe_get_all_records(self.metadata_ws)
            row_idx = None
            
            for idx, record in enumerate(all_records, start=2):  # start=2 pula header
                if record.get("Tab Name") == tab_name:
                    row_idx = idx
                    break
            
            if row_idx:
                # Atualiza registro existente
                self.metadata_ws.update(f"B{row_idx}:D{row_idx}", [[timestamp, user_id, data_hash or ""]])
            else:
                # Cria novo registro
                self.metadata_ws.append_row([tab_name, timestamp, user_id, data_hash or ""])
                
        except Exception as e:
            # Não bloqueia operação se falhar
            pass
    
    def get_last_modified(self, tab_name: str) -> Optional[Dict[str, Any]]:
        """
        Retorna informações da última modificação de uma aba.
        
        Returns:
            {"timestamp": datetime, "user": str, "hash": str} ou None
        """
        try:
            all_records = safe_get_all_records(self.metadata_ws)
            
            for record in all_records:
                if record.get("Tab Name") == tab_name:
                    timestamp_str = record.get("Last Modified", "")
                    try:
                        timestamp = datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M:%S")
                    except:
                        timestamp = None
                    
                    return {
                        "timestamp": timestamp,
                        "user": record.get("Modified By", ""),
                        "hash": record.get("Change Hash", "")
                    }
            
            return None
            
        except Exception as e:
            return None
    
    def has_changes_since(self, tab_name: str, since: datetime) -> bool:
        """
        Verifica se houve mudanças desde um timestamp.
        
        Args:
            tab_name: Nome da aba
            since: Timestamp de referência
            
        Returns:
            True se houve mudanças, False caso contrário
        """
        last_mod = self.get_last_modified(tab_name)
        if not last_mod or not last_mod["timestamp"]:
            return False
        
        return last_mod["timestamp"] > since
    
    @staticmethod
    def compute_data_hash(data: Any) -> str:
        """
        Computa hash de dados para detecção de mudanças.
        
        Args:
            data: Dados para hash (dict, list, DataFrame, etc)
            
        Returns:
            Hash MD5 dos dados
        """
        try:
            # Converte para JSON string e computa hash
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.md5(data_str.encode()).hexdigest()
        except:
            return ""
    
    def get_active_users(self, minutes: int = 5) -> list:
        """
        Retorna lista de usuários ativos nos últimos N minutos.
        
        Args:
            minutes: Janela de tempo em minutos
            
        Returns:
            Lista de user IDs únicos
        """
        try:
            all_records = safe_get_all_records(self.metadata_ws)
            cutoff = datetime.now() - timedelta(minutes=minutes)
            active_users = set()
            
            for record in all_records:
                timestamp_str = record.get("Last Modified", "")
                try:
                    timestamp = datetime.strptime(timestamp_str, "%d/%m/%Y %H:%M:%S")
                    if timestamp > cutoff:
                        user = record.get("Modified By", "")
                        if user:
                            active_users.add(user)
                except:
                    continue
            
            return list(active_users)
            
        except Exception as e:
            return []


# Singleton instance cache
@st.cache_resource(ttl=3600)
def get_realtime_sync(_gspread_client, sheet_name: str = "UAEW_App") -> RealtimeSync:
    """Retorna instância singleton do RealtimeSync."""
    return RealtimeSync(_gspread_client, sheet_name)


# Componente de auto-refresh
def setup_auto_refresh(interval_ms: int = 5000, key: str = "auto_refresh") -> int:
    """
    Configura auto-refresh da página.
    
    Args:
        interval_ms: Intervalo em milissegundos
        key: Chave única para o componente
        
    Returns:
        Contador de refreshes (0 se módulo não disponível)
    """
    try:
        from streamlit_autorefresh import st_autorefresh
        return st_autorefresh(interval=interval_ms, key=key)
    except ImportError:
        # Módulo não instalado - auto-refresh desabilitado
        return 0
    except Exception as e:
        # Qualquer outro erro - auto-refresh desabilitado
        return 0


# Indicador visual de sincronização
def render_sync_indicator(last_sync: Optional[datetime] = None, active_users: list = None):
    """
    Renderiza indicador de sincronização no topo da página.
    
    Args:
        last_sync: Timestamp da última sincronização
        active_users: Lista de usuários ativos
    """
    now = datetime.now()
    
    if last_sync:
        delta = (now - last_sync).total_seconds()
        if delta < 10:
            status_color = "#28a745"  # Verde
            status_text = "🟢 Sincronizado"
        elif delta < 30:
            status_color = "#ffc107"  # Amarelo
            status_text = "🟡 Sincronizando..."
        else:
            status_color = "#dc3545"  # Vermelho
            status_text = "🔴 Desatualizado"
        
        time_ago = f"{int(delta)}s atrás" if delta < 60 else f"{int(delta/60)}m atrás"
    else:
        status_color = "#6c757d"  # Cinza
        status_text = "⚪ Carregando..."
        time_ago = ""
    
    active_count = len(active_users) if active_users else 0
    users_text = f"👥 {active_count} usuário(s) ativo(s)" if active_count > 0 else ""
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, {status_color}22 0%, transparent 100%);
        border-left: 4px solid {status_color};
        padding: 8px 15px;
        margin-bottom: 15px;
        border-radius: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.9em;
    ">
        <div>
            <strong>{status_text}</strong>
            {f'<span style="color: #999; margin-left: 10px;">{time_ago}</span>' if time_ago else ''}
        </div>
        <div style="color: #999;">
            {users_text}
        </div>
    </div>
    """, unsafe_allow_html=True)
