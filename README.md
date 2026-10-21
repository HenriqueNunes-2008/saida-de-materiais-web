# Sistema de Saída de Materiais

Aplicação web em Flask para registrar saídas de materiais, controlar saldos e custos de estoque, acompanhar devoluções e consultar relatórios. A interface segue a identidade visual FlexiMedical/Kure.

## Funcionalidades

- Autenticação, cadastro de usuários e aprovação de acesso.
- Cadastro de produtos com código, descrição, unidade, preço, estoque mínimo e gatilho de reposição.
- Registro de saldo inicial, entradas, saídas, ajustes de saldo e estornos, com histórico de movimentações.
- Consulta de estoque com filtros por código ou descrição, unidade e situação.
- Resumo de estoque calculado pelo custo médio e indicadores de reposição.
- Notificações para produtos sem saldo, no estoque mínimo ou no gatilho de reposição. Saldos pendentes de conferência não são tratados como saldo físico confirmado nos alertas.
- Relatórios de saídas com filtros por período, projeto, material, funcionário e estorno.
- Exportação Excel das saídas do mês atual, incluindo quantidades e valores históricos de estornos.
- Gerenciamento de usuários, aprovação, bloqueio e redefinição de senha por usuários autorizados.

## Perfis e permissões

| Perfil | Permissões principais |
| --- | --- |
| Almoxarifado | Cadastrar e editar produtos, registrar entradas, saídas e estornos, consultar estoque e relatórios e exportar Excel. |
| Compras | Consultar estoque e relatórios e exportar Excel. Não altera saldos nem cadastra produtos. |
| TI ou administrador autorizado | Aprovar e bloquear contas e gerenciar solicitações de redefinição de senha. |

O cadastro público aceita os setores Almoxarifado e Compras. Novas contas aguardam aprovação e ativação por TI ou por um usuário administrativo autorizado.

## Requisitos

- Python 3.10 ou superior.
- pip.
- Um banco de dados com o schema compatível com os modelos da aplicação: SQLite para desenvolvimento local ou PostgreSQL/Neon.

As dependências estão listadas em [requirements.txt](requirements.txt). A aplicação não cria tabelas nem executa migrações automaticamente. Prepare o banco e aplique as migrações necessárias manualmente antes de iniciar o servidor.

## Configuração local

1. Crie e ative um ambiente virtual na raiz do projeto:

   **Windows PowerShell**

   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

   **Linux ou macOS**

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Crie um arquivo `.env` na raiz do projeto. A configuração carrega esse arquivo e exige `SECRET_KEY` e `DATABASE_URL`. Para desenvolvimento com SQLite, use um banco local:

   ```env
   SECRET_KEY=troque-por-uma-chave-aleatoria
   DATABASE_URL=sqlite:///saida_materiais_dev.db
   SESSION_COOKIE_SECURE=false
   ```

   Gere uma chave aleatória com:

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Copie o resultado para `SECRET_KEY`. O valor `SESSION_COOKIE_SECURE=false` permite testar em `http://127.0.0.1`; em produção, sirva a aplicação por HTTPS e mantenha o cookie seguro ativado.

4. Prepare o schema do banco local antes da primeira execução. Para PostgreSQL/Neon, defina `DATABASE_URL` com a URL do banco de desenvolvimento apropriado. Não use credenciais de produção em desenvolvimento.

5. Inicie a aplicação:

   ```bash
   python app.py
   ```

   Acesse `http://127.0.0.1:5000`.

## Configuração e execução em produção

Defina `SECRET_KEY` e `DATABASE_URL` no gerenciador de variáveis de ambiente do serviço de hospedagem. A URL pode ser fornecida no formato PostgreSQL; a aplicação ajusta o esquema para usar o driver `psycopg2` instalado pelos requisitos.

O servidor WSGI incluído nos requisitos pode iniciar a aplicação com:

```bash
gunicorn app:app
```


## Telas e rotas principais

| Rota | Uso |
| --- | --- |
| `/` | Início, entrada no sistema e registro de saída conforme o perfil. |
| `/estoque` | Consulta e resumo de produtos e saldos. |
| `/estoque/cadastrar` | Cadastro de produto para Almoxarifado. |
| `/estoque/<id>` | Detalhes do produto e histórico recente de movimentações. |
| `/report` | Consulta de saídas, filtros e informações de estorno. |
| `/download_excel` | Download das saídas do mês atual em Excel. |
| `/admin` | Administração de usuários autorizada para TI ou administradores. |

As ações que alteram dados exigem autenticação, autorização por perfil e token CSRF.

## Estrutura do projeto

```text
.
├── app.py                    # Inicialização do Flask, filtros e registro de rotas
├── config.py                 # Configuração por variáveis de ambiente
├── extensions.py             # SQLAlchemy e Flask-Login
├── controllers/              # Rotas de autenticação, estoque, saídas e relatórios
├── models/                   # Modelos ORM separados por entidade
├── services/                 # Regras de estoque, saídas, relatórios e Excel
├── templates/                # Páginas HTML e componentes Jinja
├── static/                   # CSS, JavaScript e recursos visuais
├── requirements.txt          # Dependências Python
├── runtime.txt               # Versão de runtime indicada para hospedagem
└── start_app.bat             # Inicialização auxiliar no Windows
```

## Licença

Aplicação destinada ao uso interno da organização.