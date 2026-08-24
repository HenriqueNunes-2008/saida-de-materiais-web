# Saída de Materiais - FlexiMedical / Kure

Aplicação web para controle de saída de materiais com autenticação por perfil, permissões por setor e exportação de relatórios em Excel.

## Visão geral

O sistema foi pensado para atender múltiplos perfis da empresa:

- Almoxarifado:
  - registra saídas de materiais
  - acessa a tela de registros
  - exporta relatórios em Excel
- Compras:
  - visualiza saídas e relatórios
  - baixa planilhas mensais
  - não registra saídas
- TI:
  - gerencia usuários cadastrados
  - aprova ou bloqueia contas
  - redefine senhas

## Funcionalidades principais

- Login e cadastro com modal de autenticação
- Fluxo de aprovação do TI para novos usuários
- Controle de acesso por setor e perfil
- Sidebar com navegação por área
- Tela de relatório com filtros por:
  - período
  - projeto
  - material
  - funcionário
- Download de planilhas Excel mensais
- Fallback local em SQLite
- Preparação para banco PostgreSQL/Neon em ambiente de produção

## Requisitos

- Python 3.10+
- pip
- Dependências do arquivo `requirements.txt`

## Configuração local

1. Clone o repositório
2. Crie um ambiente virtual:

```bash
python -m venv venv
```

3. Ative o ambiente:

Windows:
```bash
venv\Scripts\activate
```

Linux/macOS:
```bash
source venv/bin/activate
```

4. Instale as dependências:

```bash
pip install -r requirements.txt
```

5. Configure as variáveis de ambiente:

```bash
copy .env.example .env
```

Edite o arquivo `.env` com os valores reais do projeto. A estrutura básica é:

```env
SECRET_KEY=sua_chave_secreta
DATABASE_URL=
ADMIN_EMAIL=ti@empresa.com
ADMIN_PASSWORD=sua_senha_admin
```

Observações:
- `DATABASE_URL` pode ficar vazio para usar SQLite localmente
- em produção, o ideal é utilizar PostgreSQL/Neon em variável de ambiente do hosting

## Execução

```bash
python app.py
```

A aplicação ficará disponível em:

```text
http://127.0.0.1:5000
```

## Estrutura de pastas

```text
.
├── app.py
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── static/
├── templates/
├── formatar_excel.py
├── start_app.bat
└── venv/
```

## Observações importantes

- Arquivos sensíveis como `.env` e banco local não devem ser enviados para o repositório
- O projeto usa SQLite por padrão em ambiente local e aceita `DATABASE_URL` para PostgreSQL/Neon
- Planilhas geradas no runtime são arquivos temporários e devem ficar fora do controle de versionamento

## Licença

Este projeto é destinado ao uso interno da organização e pode ser ajustado conforme regras internas da empresa.
