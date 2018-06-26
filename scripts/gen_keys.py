#!/usr/bin/env python

import json
import click


@click.command()
@click.option("--key-size", default=2048)
def gen_keys(key_size):
    try:
        from jwcrypto.jwk import JWK, JWKSet
    except ImportError as e:
        msg = "You have to install jwcrypto to use this function"
        print(msg)
        raise ImportError(msg) from e

    jwk = JWK()
    jwk.generate_key(generate="RSA", size=key_size)

    contents = jwk.export_to_pem(private_key=True, password=None)
    with open("private.pem", "w") as priv_pem_file:
        priv_pem_file.write(contents.decode("utf8"))

    contents = jwk.export_to_pem(private_key=False, password=None)
    with open("public.pem", "w") as priv_pem_file:
        priv_pem_file.write(contents.decode("utf8"))

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
    gen_keys()
