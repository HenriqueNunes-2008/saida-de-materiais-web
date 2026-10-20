"""Flask entry point. Legacy endpoint names retained for template compatibility."""
import os
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask
from config import Config
from extensions import db, login_manager
from models import User
from controllers import saida_controller, cadastro_controller, auth_controller, admin_controller, relatorio_controller, estoque_controller
from controllers.estoque_controller import csrf_token


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.globals['csrf_value'] = csrf_token
    @app.template_filter("qtd")
    def format_quantity(value):
        """Exibe até três decimais, omitindo zeros à direita."""
        if value is None:
            return "—"
        number = Decimal(str(value))
        return format(number.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".").replace(".", ",") if number != 0 else "0"

    @app.template_filter("br_num")
    def format_brazilian_number(value, decimals=2):
        """Formata numeros com ponto de milhar e virgula decimal."""
        if value is None:
            return "—"
        places = max(0, min(int(decimals), 6))
        number = Decimal(str(value))
        quantum = Decimal(1).scaleb(-places)
        localized = format(number.quantize(quantum, rounding=ROUND_HALF_UP), f",.{places}f")
        return localized.replace(",", "\0").replace(".", ",").replace("\0", ".")

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        try:
            user = db.session.get(User, int(user_id))
            return user if user and user.active and user.approved else None
        except (TypeError, ValueError):
            return None

    for controller in (saida_controller, cadastro_controller, auth_controller,
                       admin_controller, relatorio_controller, estoque_controller):
        controller.register_routes(app)
    return app


app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
