import json
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound

from calendar import weekday, monthrange, monthcalendar
from datetime import datetime, timedelta


DEBIT_PERIODS = {'biweekly': 14,
                 'weekly': 7}

DEBIT_WEEKDAY = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}


class App(object):

    def __init__(self):
        self.url_map = Map(
            [
                Rule("/", endpoint=""),
                Rule("/get_next_debit", endpoint="get_next_debit")
            ]
        )

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, f"on_{endpoint}")(request, **values)
        except NotFound:
            return self.error_404()
        except HTTPException as e:
            return e

    def on_get_next_debit(self, request):
        """

        request:   {
                            "loan": {
                                "monthly_payment_amount": 750,
                                "payment_due_day": 28,
                                "schedule_type": "biweekly",
                                "debit_start_date": "2021-05-07",
                                "debit_day_of_week": "friday"
                            }
                        }

        response: {
                    "debit": {
                        "amount": 375,
                        "date": "2021-05-21"
                    }
                  }
        """
        body = request.get_json().get('loan')

        # Get all of the data since we don't have a serializer yet
        current_date = datetime.now().date()
        year = current_date.year
        month = current_date.month
        day = current_date.day
        schedule_type = body.get('schedule_type')
        monthly_pay = body.get('monthly_payment_amount')

        # Get the business day integer so we can count how many are in the month using calendar
        business_day = DEBIT_WEEKDAY.get(body.get('debit_day_of_week'))
        start_date = datetime.strptime(body.get('debit_start_date'), "%Y-%m-%d").date()

        num_debit_days = 0
        for d in range(1, monthrange(year, month)[1] + 1):
            if weekday(year, month, d) == business_day:
                num_debit_days += 1

        if schedule_type == 'biweekly':
            amount = monthly_pay / (num_debit_days / 2)

        next_date = start_date + timedelta(days=14)
        response = {'debit':
                            {
                                'amount': amount,
                                'date': str(next_date)
                            }
                    }

        return Response(json.dumps(response), mimetype='application/json')

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app():
    app = App()
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple

    app = create_app()
    run_simple('0.0.0.0', 5000, app, use_debugger=True, use_reloader=True)
