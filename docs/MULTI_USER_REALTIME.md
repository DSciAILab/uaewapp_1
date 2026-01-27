# Multi-Usuário e Tempo Real - Documentação

## 📋 Visão Geral

Este documento descreve as melhorias implementadas no sistema UAEW Operations App para suportar **múltiplos usuários simultâneos** e **atualizações em tempo real**, mantendo o Google Sheets como backend.

---

## ✅ Melhorias Implementadas

### 1. **Sistema de Locks (Controle de Concorrência)**

**Arquivo:** `locks_manager.py`

**Funcionalidade:**
- Previne conflitos quando múltiplos usuários editam o mesmo atleta
- Locks automáticos com timeout de 5 minutos
- Cleanup automático de locks expirados
- Fail-open (permite operação em caso de erro)

**Como Funciona:**
```python
# Antes de editar um atleta
success, locked_by = lock_manager.acquire_lock(athlete_id, athlete_name, user_id)

if not success:
    st.warning(f"⚠️ Atleta bloqueado por {locked_by}")
else:
    # Permite edição
    # ...
    # Libera lock após salvar
    lock_manager.release_lock(athlete_id, user_id)
```

**Estrutura no Google Sheets:**
- Nova aba: `Locks`
- Colunas: `Lock ID`, `Athlete ID`, `Athlete Name`, `Locked By`, `Locked At`, `Expires At`

---

### 2. **Sincronização em Tempo Real**

**Arquivo:** `realtime_utils.py`

**Funcionalidades:**

#### a) Auto-Refresh (5 segundos)
- Atualiza dados automaticamente a cada 5 segundos
- Limpa cache para forçar reload
- Usa `streamlit-autorefresh` (já instalado)

#### b) Tracking de Mudanças
- Registra timestamp de cada modificação
- Identifica usuário que fez a mudança
- Permite detecção de dados desatualizados

#### c) Indicador Visual de Sincronização
- 🟢 Verde: Sincronizado (< 10s)
- 🟡 Amarelo: Sincronizando (10-30s)
- 🔴 Vermelho: Desatualizado (> 30s)
- Mostra número de usuários ativos

**Estrutura no Google Sheets:**
- Nova aba: `Sync_Metadata`
- Colunas: `Tab Name`, `Last Modified`, `Modified By`, `Change Hash`

---

### 3. **Cache Otimizado**

**Arquivos Modificados:** `utils.py`, `task_app.py`

**Mudanças:**
- ❌ Antes: TTL de 600s (10 minutos)
- ✅ Agora: TTL de 30s

**Impacto:**
- Dados ficam desatualizados por no máximo 30 segundos
- Combinado com auto-refresh (5s), garante sincronização rápida
- Reduz conflitos entre usuários

---

### 4. **Feedback Visual Aprimorado**

**Melhorias na UI:**

#### a) Indicador de Sincronização (Topo da Página)
```
🟢 Sincronizado | 3s atrás | 👥 2 usuário(s) ativo(s)
```

#### b) Indicador de Lock (Cards de Atletas)
```
🔒 Bloqueado por João Silva
```

#### c) Buffer de Mudanças Pendentes
- Contador visual de mudanças não salvas
- Botão "💾 Salvar tudo" destacado quando há pendências
- Auto-limpeza após salvar

---

## 🚀 Como Usar

### Para Desenvolvedores

#### 1. Integração em Nova Página

```python
from task_app import render_task_page

# Em qualquer página que use task_app
render_task_page(
    page_title="Minha Página",
    fixed_task="Nome da Task",
    task_aliases=["Alias1", "Alias2"]
)
# Auto-refresh e locks já estão ativos!
```

#### 2. Verificar Lock Manualmente

```python
from locks_manager import get_lock_manager
from utils import get_gspread_client

gc = get_gspread_client()
lock_manager = get_lock_manager(gc)

is_locked, locked_by = lock_manager.check_lock_status(athlete_id)
if is_locked:
    st.warning(f"Bloqueado por {locked_by}")
```

#### 3. Registrar Mudança Manual

```python
from realtime_utils import get_realtime_sync
from utils import get_gspread_client

gc = get_gspread_client()
realtime_sync = get_realtime_sync(gc)

# Após modificar dados
realtime_sync.record_change(
    tab_name="Attendance",
    user_id=st.session_state.get('current_user_id')
)
```

---

### Para Usuários Finais

#### 1. **Indicador de Sincronização**
- Sempre visível no topo da página
- Verde = dados atualizados
- Vermelho = clique em "🔄 Recarregar dados"

#### 2. **Edição Simultânea**
- Se outro usuário está editando um atleta, você verá:
  ```
  ⚠️ Atleta bloqueado por João Silva
  Aguarde alguns minutos ou contate o usuário.
  ```

#### 3. **Salvamento**
- **Importante:** Clique em "💾 Salvar tudo" antes de sair
- Mudanças não salvas são perdidas ao fechar o navegador
- Contador mostra quantas mudanças estão pendentes

---

## 📊 Cenários de Uso

### Cenário 1: Dois Usuários Editam Atletas Diferentes
```
Usuário A edita Atleta 1 → Lock adquirido
Usuário B edita Atleta 2 → Lock adquirido
Ambos salvam → Sem conflitos ✅
```

### Cenário 2: Dois Usuários Tentam Editar Mesmo Atleta
```
Usuário A edita Atleta 1 → Lock adquirido
Usuário B tenta editar Atleta 1 → ⚠️ Bloqueado
Usuário A salva e libera lock
Usuário B pode editar agora ✅
```

### Cenário 3: Lock Expira (Usuário Esqueceu de Salvar)
```
Usuário A edita Atleta 1 → Lock adquirido
Usuário A não salva e fecha navegador
Após 5 minutos → Lock expira automaticamente
Usuário B pode editar ✅
```

### Cenário 4: Dados Desatualizados
```
Usuário A marca Atleta 1 como "Done" às 14:00
Usuário B abriu página às 13:55 (cache válido)
Auto-refresh (5s) detecta mudança
Usuário B vê "Done" em até 30s ✅
```

---

## ⚙️ Configurações

### Ajustar Intervalo de Auto-Refresh

**Arquivo:** `realtime_utils.py`
```python
class RealtimeSync:
    REFRESH_INTERVAL_MS = 5000  # 5 segundos (padrão)
    # Altere para 3000 (3s) ou 10000 (10s) conforme necessário
```

### Ajustar Timeout de Locks

**Arquivo:** `locks_manager.py`
```python
class LockManager:
    LOCK_TIMEOUT_MINUTES = 5  # 5 minutos (padrão)
    # Altere para 3 ou 10 conforme necessário
```

### Ajustar TTL do Cache

**Arquivo:** `task_app.py`
```python
@st.cache_data(ttl=30, show_spinner=False)  # 30 segundos (padrão)
def load_athlete_data(...):
    # Altere para 15 (mais rápido) ou 60 (mais lento)
```

---

## 🔧 Troubleshooting

### Problema: Auto-refresh não funciona
**Solução:**
```bash
pip install streamlit-autorefresh
```

### Problema: Locks não aparecem no Google Sheets
**Solução:**
- Verifique permissões da conta de serviço
- Aba "Locks" é criada automaticamente na primeira execução
- Se não existir, crie manualmente com as colunas especificadas

### Problema: Indicador sempre vermelho
**Solução:**
- Verifique conexão com Google Sheets API
- Limpe cache: Botão "🔄 Recarregar dados (forçado)"
- Verifique se aba "Sync_Metadata" existe

### Problema: Muitos usuários ativos (performance)
**Solução:**
- Aumente TTL do cache (de 30s para 60s)
- Aumente intervalo de auto-refresh (de 5s para 10s)
- Considere migrar para Supabase (próxima fase)

---

## 📈 Métricas de Performance

### Antes das Melhorias
- ❌ Cache: 10 minutos
- ❌ Refresh: Manual
- ❌ Conflitos: Não detectados
- ❌ Sincronização: Até 10 minutos de atraso

### Depois das Melhorias
- ✅ Cache: 30 segundos
- ✅ Refresh: Automático (5s)
- ✅ Conflitos: Detectados e prevenidos
- ✅ Sincronização: Até 30 segundos de atraso

---

## 🎯 Próximas Melhorias (Futuro)

### Fase 3: Migração para Supabase
- WebSocket para sincronização instantânea (< 1s)
- Transações ACID (sem race conditions)
- Auditoria automática (histórico de mudanças)
- Escalabilidade para 100+ usuários

### Melhorias Incrementais
- [ ] Notificações push quando outro usuário edita
- [ ] Chat integrado entre usuários ativos
- [ ] Histórico de mudanças (quem mudou o quê)
- [ ] Rollback de mudanças (desfazer)
- [ ] Modo offline (sincroniza ao reconectar)

---

## 📞 Suporte

Para dúvidas ou problemas:
1. Verifique este documento primeiro
2. Consulte logs no terminal (erros aparecem lá)
3. Teste em ambiente de desenvolvimento antes de produção

---

**Última atualização:** 27/01/2026
**Versão:** 2.0 (Multi-user + Realtime)
