# Bot Caçador de Leads (TI) - Guia Completo

## 📋 Visão Geral

O **Email Hunter** é uma ferramenta automatizada para coleta de emails de empresas de tecnologia que estão com vagas abertas. Ele realiza varreduras na web usando múltiplas fontes e inteligência artificial para identificar e extrair contatos de RH/recrutamento.

## 🚀 Funcionalidades

### Principais Recursos
- **Busca Automatizada**: Varre múltiplas fontes (LinkedIn Jobs, Gupy, Vagas.com.br, Indeed, GitHub Jobs, Stack Overflow Jobs, etc.)
- **IA para Extração**: Usa Gemini AI para analisar resultados e extrair leads válidos
- **Múltiplas Localizações**: Suporte a vagas presenciais (Recife, SP, RJ, Portugal) e remotas
- **Filtro por Tech Stack**: Foco em Python, FastAPI, React, Node.js, Full Stack, DevOps, etc.
- **Priorização de Emails**: Identifica emails institucionais de RH/recrutamento
- **Exportação Flexível**: CSV e JSON compatível com o sistema de envio de emails

### Fontes de Busca
1. LinkedIn Jobs
2. Gupy.io
3. VAGAS.com.br
4. Indeed Brasil
5. GitHub Jobs
6. Stack Overflow Jobs
7. Glassdoor
8. Programathor
9. GeekHunter
10. 99Jobs
11. Trampos.co
12. Porto Digital
13. E muitas outras...

## 📦 Instalação

### Pré-requisitos
- Python 3.8+
- Chave de API do Google Gemini (opcional, para extração com IA)
- Conexão com internet

### Dependências
```bash
pip install requests beautifulsoup4 google-generativeai python-dotenv duckduckgo-search
```

Ou instale todas as dependências do projeto:
```bash
pip install -r requirements.txt
```

### Configuração da API Gemini (Opcional)
1. Obtenha uma chave em [Google AI Studio](https://aistudio.google.com/)
2. Adicione no arquivo `config.env`:
```
GEMINI_API_KEY=sua_chave_aqui
```

## 🎯 Como Usar

### Execução Básica
```bash
# Executar busca automática completa
python tools/email_hunter.py
```

### Comandos Disponíveis

#### 1. Busca Automática
```bash
# Executa todas as queries (padrão: 20 buscas)
python tools/email_hunter.py

# Limita número de queries (útil para testes)
python tools/email_hunter.py --max-queries 5
```

#### 2. Busca Direcionada
```bash
# Busca emails para empresas listadas no JSON
python tools/email_hunter.py --hunt-companies
```

#### 3. Exportação
```bash
# Exporta leads atuais para CSV e JSON
python tools/email_hunter.py --export-csv
```

#### 4. Estatísticas
```bash
# Mostra estatísticas do banco de leads
python tools/email_hunter.py --stats
```

#### 5. Ajuda
```bash
# Mostra todas as opções
python tools/email_hunter.py --help
```

## 📁 Arquivos de Saída

### `data/leads_ti.json`
Banco principal de leads em formato JSON:
```json
[
  {
    "empresa": "Tech Solutions Ltda",
    "site": "www.techsolutions.com.br",
    "email": "rh@techsolutions.com.br",
    "cargo_da_vaga": "Desenvolvedor Python",
    "fonte": "LinkedIn",
    "data": "2024-10-05"
  }
]
```

### `data/leads_ti.csv`
Versão CSV para planilhas:
```csv
empresa,site,email,cargo_da_vaga,fonte,data
Tech Solutions Ltda,www.techsolutions.com.br,rh@techsolutions.com.br,Desenvolvedor Python,LinkedIn,2024-10-05
```

### `data/leads_compilado_hunter.json`
Formato compatível com o sistema de envio de emails:
```json
{
  "metadata": {
    "titulo": "Leads Coletados - Email Hunter",
    "descricao": "Empresas de TI com vagas ativas",
    "gerado_em": "2024-10-05",
    "total_leads": 50
  },
  "agencias_rh": [
    {
      "nome": "Tech Solutions Ltda",
      "email": "rh@techsolutions.com.br",
      "regiao": "Brasil",
      "especialidade": "Desenvolvedor Python"
    }
  ]
}
```

## ⚙️ Personalização

### Adicionar Novas Fontes
Edite a lista `PREFIXES` no início do arquivo:
```python
PREFIXES = [
    # ... fontes existentes ...
    'site:novasite.com "tecnologia"',
    'site:outrasite.com.br "vagas"',
]
```

### Alterar Termos de Busca
Edite a lista `ROLES`:
```python
ROLES = [
    "python", "fastapi", "react",
    "sua_tecnologia_aqui",  # Adicione novas tecnologias
]
```

### Alterar Localizações
Edite as listas `LOCATIONS_PRESENCIAL` e `LOCATIONS_REMOTE`:
```python
LOCATIONS_PRESENCIAL = [
    "recife", "pernambuco",
    "sua_cidade_aqui",  # Adicione novas cidades
]
```

### Ajustar Intervalos de Requisição
Para evitar bloqueios, ajuste os delays:
```python
# No final do run_hunter():
delay = random.uniform(12, 16)  # Aumente se estiver sendo bloqueado
```

## 🔧 Integração com o Bot Principal

Os leads coletados podem ser usados pelo bot de candidatura automática:

1. **Via JSON compilado**:
   - O arquivo `leads_compilado_hunter.json` é automaticamente lido pelo `main.py`
   - Execute: `python main.py --manual` para processar apenas emails manuais

2. **Via banco de leads**:
   - Os leads em `data/leads_ti.json` podem ser processados pelo módulo `company_researcher.py`

## 🛡️ Boas Práticas

### Rate Limiting
- O bot já inclui delays automáticos entre requisições
- Não remova os delays para evitar bloqueios de IP

### Qualidade dos Emails
- Apenas emails institucionais são coletados
- Emails pessoais (gmail, outlook, etc.) são filtrados
- Emails de RH/recrutamento são priorizados

### Respeito aos Sites
- O bot respeita robots.txt implicitamente
- Não faz scraping agressivo
- Usa user-agents legítimos

## 🐛 Solução de Problemas

### "Nenhum lead encontrado"
- Verifique se a API do Gemini está configurada (opcional, mas recomendado)
- Aumente o número de queries: `--max-queries 30`
- Execute em horários diferentes (sites podem ter conteúdo dinâmico)

### "Bloqueio de IP"
- Aumente os delays entre requisições
- Use VPN ou proxy rotativo
- Execute menos queries por sessão

### "API Gemini com erro"
- Verifique se a chave está correta no `config.env`
- A ferramenta funciona sem IA, mas com menos precisão

### "DuckDuckGo não retorna resultados"
- Verifique sua conexão com internet
- DuckDuckGo pode estar temporariamente indisponível
- Tente novamente após alguns minutos

## 📊 Estatísticas e Métricas

Use `--stats` para ver:
- Total de leads no banco
- Distribuição por fonte
- Emails HR vs outros
- Caminhos dos arquivos de exportação

## 🔄 Fluxo de Trabalho Recomendado

1. **Coleta Inicial**:
   ```bash
   python tools/email_hunter.py --max-queries 10
   ```

2. **Exportar para análise**:
   ```bash
   python tools/email_hunter.py --export-csv
   ```

3. **Processar no bot principal**:
   ```bash
   python main.py --manual
   ```

4. **Verificar resultados**:
   ```bash
   python main.py --status
   ```

## 📝 Exemplos de Uso

### Exemplo 1: Coleta Rápida para Testes
```bash
# Coleta apenas 5 queries para teste
python tools/email_hunter.py --max-queries 5

# Verifica o resultado
python tools/email_hunter.py --stats
```

### Exemplo 2: Coleta Completa
```bash
# Executa coleta completa (20 queries)
python tools/email_hunter.py

# Exporta resultados
python tools/email_hunter.py --export-csv

# Usa no bot principal
python main.py --manual
```

### Exemplo 3: Coleta Direcionada
```bash
# Busca emails para empresas específicas do JSON
python tools/email_hunter.py --hunt-companies

# Exporta resultados
python tools/email_hunter.py --export-csv
```

## 🤝 Contribuição

Para adicionar novas funcionalidades:

1. **Novas fontes de busca**: Adicione à lista `PREFIXES`
2. **Novos padrões de email**: Adicione à lista `HR_EMAIL_PREFIXES`
3. **Melhorias na IA**: Ajuste o prompt em `extract_leads_with_gemini()`

## 📄 Licença

Este projeto segue a mesma licença do repositório principal.

## 🔗 Links Úteis

- [Repositório Principal](https://github.com/pauloneto98/Bot_BuscaVagas)
- [Documentação do Bot Principal](../README.md)
- [Google AI Studio](https://aistudio.google.com/)
- [DuckDuckGo API](https://pypi.org/project/duckduckgo-search/)

---

**Desenvolvido com ❤️ para automatizar a busca por oportunidades em TI**