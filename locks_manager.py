# locks_manager.py
"""
Sistema de controle de concorrência para multi-usuário usando Google Sheets.
Implementa locks otimistas para prevenir conflitos de edição.
"""

import streamlit as st
from utils import safe_get_all_records
from datetime import datetime, timedelta
from typing import Optional, Tuple
import time

class LockManager:
    """Gerencia locks de edição para prevenir conflitos entre usuários."""
    
    LOCK_TIMEOUT_MINUTES = 5  # Auto-release após 5 minutos
    LOCKS_TAB_NAME = "Locks"
    
    def __init__(self, gspread_client, sheet_name: str = "UAEW_App"):
        self.gc = gspread_client
        self.sheet_name = sheet_name
        self._ensure_locks_tab()
    
    def _ensure_locks_tab(self):
        """Cria aba 'Locks' se não existir."""
        try:
            spreadsheet = self.gc.open(self.sheet_name)
            try:
                self.locks_ws = spreadsheet.worksheet(self.LOCKS_TAB_NAME)
            except Exception:
                # Cria aba se não existir
                self.locks_ws = spreadsheet.add_worksheet(
                    title=self.LOCKS_TAB_NAME,
                    rows=1000,
                    cols=6
                )
                # Header
                self.locks_ws.append_row([
                    "Lock ID", "Athlete ID", "Athlete Name", 
                    "Locked By", "Locked At", "Expires At"
                ])
        except Exception as e:
            st.error(f"Erro ao inicializar sistema de locks: {e}", icon="🚨")
    
    def _parse_datetime(self, dt_str: str) -> Optional[datetime]:
        """Parse datetime string from Google Sheets."""
        if not dt_str:
            return None
        try:
            return datetime.strptime(dt_str, "%d/%m/%Y %H:%M:%S")
        except:
            try:
                return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            except:
                return None
    
    def _cleanup_expired_locks(self):
        """Remove locks expirados."""
        try:
            all_locks = safe_get_all_records(self.locks_ws)
            now = datetime.now()
            
            rows_to_delete = []
            for idx, lock in enumerate(all_locks, start=2):  # start=2 pula header
                expires_at = self._parse_datetime(lock.get("Expires At", ""))
                if expires_at and now > expires_at:
                    rows_to_delete.append(idx)
            
            # Delete de trás pra frente para não afetar índices
            for row_idx in sorted(rows_to_delete, reverse=True):
                self.locks_ws.delete_rows(row_idx)
                
        except Exception as e:
            # Não bloqueia operação se cleanup falhar
            pass
    
    def acquire_lock(
        self, 
        athlete_id: str, 
        athlete_name: str, 
        user_id: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Tenta adquirir lock para um atleta.
        
        Returns:
            (success: bool, locked_by: Optional[str])
            - (True, None) se lock adquirido
            - (False, "User X") se já bloqueado por outro usuário
        """
        try:
            self._cleanup_expired_locks()
            
            # Verifica se já existe lock ativo
            all_locks = safe_get_all_records(self.locks_ws)
            now = datetime.now()
            
            for lock in all_locks:
                if str(lock.get("Athlete ID", "")) == str(athlete_id):
                    expires_at = self._parse_datetime(lock.get("Expires At", ""))
                    locked_by = lock.get("Locked By", "")
                    
                    # Se lock ainda válido e não é o mesmo usuário
                    if expires_at and now < expires_at:
                        if locked_by != user_id:
                            return False, locked_by
                        else:
                            # Mesmo usuário, renova lock
                            return True, None
            
            # Cria novo lock
            lock_id = f"{athlete_id}_{int(time.time())}"
            locked_at = now.strftime("%d/%m/%Y %H:%M:%S")
            expires_at = (now + timedelta(minutes=self.LOCK_TIMEOUT_MINUTES)).strftime("%d/%m/%Y %H:%M:%S")
            
            self.locks_ws.append_row([
                lock_id,
                str(athlete_id),
                str(athlete_name),
                str(user_id),
                locked_at,
                expires_at
            ])
            
            return True, None
            
        except Exception as e:
            st.warning(f"Erro ao adquirir lock: {e}. Continuando sem lock.", icon="⚠️")
            # Em caso de erro, permite operação (fail-open)
            return True, None
    
    def release_lock(self, athlete_id: str, user_id: str) -> bool:
        """
        Libera lock de um atleta.
        
        Returns:
            True se lock foi liberado, False caso contrário
        """
        try:
            all_locks = safe_get_all_records(self.locks_ws)
            
            for idx, lock in enumerate(all_locks, start=2):  # start=2 pula header
                if (str(lock.get("Athlete ID", "")) == str(athlete_id) and 
                    str(lock.get("Locked By", "")) == str(user_id)):
                    self.locks_ws.delete_rows(idx)
                    return True
            
            return False
            
        except Exception as e:
            st.warning(f"Erro ao liberar lock: {e}", icon="⚠️")
            return False
    
    def get_active_locks(self) -> dict:
        """
        Retorna dicionário de locks ativos.
        
        Returns:
            {athlete_id: {"locked_by": user, "expires_at": datetime}}
        """
        try:
            self._cleanup_expired_locks()
            all_locks = safe_get_all_records(self.locks_ws)
            now = datetime.now()
            
            active_locks = {}
            for lock in all_locks:
                athlete_id = str(lock.get("Athlete ID", ""))
                expires_at = self._parse_datetime(lock.get("Expires At", ""))
                
                if expires_at and now < expires_at:
                    active_locks[athlete_id] = {
                        "locked_by": lock.get("Locked By", ""),
                        "athlete_name": lock.get("Athlete Name", ""),
                        "expires_at": expires_at
                    }
            
            return active_locks
            
        except Exception as e:
            return {}
    
    def check_lock_status(self, athlete_id: str) -> Tuple[bool, Optional[str]]:
        """
        Verifica se atleta está bloqueado.
        
        Returns:
            (is_locked: bool, locked_by: Optional[str])
        """
        active_locks = self.get_active_locks()
        if str(athlete_id) in active_locks:
            return True, active_locks[str(athlete_id)]["locked_by"]
        return False, None


# Singleton instance cache
@st.cache_resource(ttl=3600)
def get_lock_manager(_gspread_client, sheet_name: str = "UAEW_App") -> LockManager:
    """Retorna instância singleton do LockManager."""
    return LockManager(_gspread_client, sheet_name)
