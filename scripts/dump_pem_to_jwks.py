#!/usr/bin/env python

import json
import click


@click.command()
@click.option("--in-private")
def dump_pem_to_jwks(in_private):
    try:
        from jwcrypto.jwk import JWK, JWKSet
    except ImportError as e:
        msg = "You have to install jwcrypto to use this function"
        print(msg)
        raise ImportError(msg) from e

    with open(in_private, "rb") as privfile:
        data = privfile.read()

    jwk = JWK()
    jwk.import_from_pem(data)

    jwks = JWKSet()
    jwks.add(jwk)

    raw = jwks.export(private_keys=True)
    formatted = json.dumps(json.loads(raw), indent=2)
    with open("private.json", "w") as priv_jwks_file:
        priv_jwks_file.write(formatted)

    raw = jwks.export(private_keys=False)
    formatted = json.dumps(json.loads(raw), indent=2)
    with open("public.json", "w") as public_jwks_file:
        public_jwks_file.write(formatted)


if __name__ == "__main__":
    dump_pem_to_jwks()
