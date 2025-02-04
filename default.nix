{ lib
, python3Packages
, fetchFromGitHub
, fetchPypi

, configFile ? null
}:
let
  flask-markdown = python3Packages.buildPythonPackage rec {
    pname = "Flask-Markdown";
    # not actually released, needs to make setuptools happy
    version = "0.4";
    
    src = fetchFromGitHub {
      owner = "dcolish";
      repo = "flask-markdown";
      rev = "03f8fcc38e9aebd39a2f06ce162ce859b6797fa4";
      hash = "sha256-YCKFasj4uNJw5zrV8bJD4gXPUc80ry6dMCcqkEjeAYA=";
    };

    patches = [ ./flask-markdown.patch ];
    postPatch = ''
      substituteInPlace setup.py \
        --replace-fail "version='dev'" "version='${version}'"
    '';

    build-system = with python3Packages; [ setuptools ];
  };
  is-safe-url = python3Packages.buildPythonPackage rec {
    pname = "is_safe_url";
    version = "1.0";

    src = fetchPypi {
      inherit pname version;
      hash = "sha256-13YYb2h3IR2u/eahjaHfUg3phaWCspPnqiTqHfHNWrs=";
    };

    dependencies = with python3Packages; [
      flask
      markdown
    ];

    build-system = with python3Packages; [ setuptools ];
  };
in
python3Packages.buildPythonPackage {
  pname = "lorry";
  version = "0.1";

  src = ./.;

  postPatch = lib.optionalString (configFile != null) ''
    ln -s "${configFile}" lorryserver/config.py
  '';

  build-system = with python3Packages; [ setuptools ];

  dependencies = with python3Packages; [
    flask
    flask-sqlalchemy
    psycopg2-binary
    flask-login
    wtforms
    email-validator
    flask-wtf
    flask-markdown
    flask-caching
    is-safe-url
    passlib
    dicttoxml
    python-slugify
  ];

  meta = {
    homepage = "https://github.com/openclonk/lorry";
    description = "A package manager backend and web-frontend for OpenClonk user modifications.";
    licenses = [ lib.licenses.mit ];
    maintainers = with lib.maintainers; [ lluchs ];
  };
}
