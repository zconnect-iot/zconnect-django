from django.conf import settings
from flask import Flask, jsonify, request
from flask_cors import CORS

from .sampler import Sampler


def handle_err(error):
    try:
        return jsonify({"description": error.description}), error.code
    except AttributeError:
        return jsonify({"description": "unhandled exception"}), 500


def get_flask_server():
    """Get a flask server to host the sampling endpoint

    This always hosts the endpoint, but if the sampler isn't enabled then it
    will return nothing.
    """
    app = Flask(__name__)
    CORS(app)
    app.errorhandler(Exception)(handle_err)

    sampler = Sampler()

    def dump_stats():
        reset = request.args.get("reset")

        result = sampler.output_stats()

        if reset:
            sampler.reset()

        return result, 200

    app.route("/stats/stacksampler", methods=["GET"])(dump_stats)

    if settings.ENABLE_STACKSAMPLER:
        sampler.start()

    return app
