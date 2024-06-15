# Copyright (c) 2022-2024, Abilian SAS
#
# SPDX-License-Identifier: MIT
"""Main module."""

from __future__ import annotations

import enum
import os
from http.client import OK
from pathlib import Path

from flask import Flask, Response, send_from_directory, request

from .npm import NPM
from .tags import make_tag

ONE_YEAR = 60 * 60 * 24 * 365


# Sentinel enum value used to indicate that Vite assets should be embedded with the same host as the current request.
class ViteAssetHost(enum.StrEnum):
    any = '<vite_asset_host>'


class Vite:
    app: Flask | None = None
    npm: NPM | None = None

    def __init__(self, app: Flask | None = None, vite_asset_host: str | ViteAssetHost | None = None):
        self.app = app
        self.vite_asset_host = str(vite_asset_host) if vite_asset_host else None

        if app is not None:
            self.init_app(app, vite_asset_host=vite_asset_host)

    def init_app(self, app: Flask, vite_asset_host: str | ViteAssetHost | None = None):
        self.vite_asset_host = str(vite_asset_host) if vite_asset_host else None

        if "vite" in app.extensions:
            raise RuntimeError(
                "This extension is already registered on this Flask app."
            )

        app.extensions["vite"] = self

        config = app.config
        if config.get("VITE_AUTO_INSERT", False):
            app.after_request(self.after_request)

        npm_bin_path = config.get("VITE_NPM_BIN_PATH", "npm")
        self.npm = NPM(cwd=str(self._get_root()), npm_bin_path=npm_bin_path)

        app.route("/_vite/<path:filename>", endpoint='vite.static', host=vite_asset_host)(self.vite_static)
        app.template_global("vite_tags")(make_tag)

    def after_request(self, response: Response):
        if response.status_code != OK:
            return response

        mimetype = response.mimetype or ""
        if not mimetype.startswith("text/html"):
            return response

        if not isinstance(response.response, list):
            return response

        body = b"".join(response.response).decode()

        if self.vite_asset_host == ViteAssetHost.any:
            tag = make_tag(vite_asset_host=request.host)
        else:
            tag = make_tag()

        body = body.replace("</head>", f"{tag}\n</head>")
        response.response = [body.encode("utf8")]
        response.content_length = len(response.response[0])
        return response

    def vite_static(self, filename, **kwargs):
        dist = str(self._get_root() / "dist" / "assets")
        return send_from_directory(dist, filename, max_age=ONE_YEAR)

    def _get_root(self) -> Path:
        return Path(os.getcwd()) / "vite"
