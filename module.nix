{ config, lib, pkgs, ... }:

let
  user = "lorry";
  group = user;
  cfg = config.services.lorry;
  webserver = config.services.caddy;
  lorryConfig = pkgs.writeTextFile {
    name = "config.py";
    checkPhase = ''
      ${pkgs.python3}/bin/python -m py_compile "$target"
    '';
    text = ''
      DEBUG = False
      SESSION_COOKIE_SAMESITE = "Lax"

      SQLALCHEMY_TRACK_MODIFICATIONS = False

      CACHE_TYPE = "RedisCache"
      CACHE_REDIS_URL = "unix://${config.services.redis.servers.lorry.unixSocket}"
      
      OWN_HOST = "${cfg.hostname}"
      RESOURCES_PATH = "${cfg.resourcesPath}"
      ALLOWED_FILE_EXTENSIONS = ("ocs", "ocf", "ocd")

      ${lib.optionalString cfg.enablePostgres ''
        SQLALCHEMY_DATABASE_URI = "postgresql://${user}@/${user}?host=/run/postgresql"
      ''}

      ${cfg.extraConfig}
      ${lib.optionalString (cfg.configFilePath != null) ''
        import runpy
        globals().update(runpy.run_path('${cfg.configFilePath}'))
      ''}
    '';
  };
  pkg = cfg.package.override { configFile = lorryConfig; };
  pythonEnv = pkgs.python3.withPackages (ps: [ ps.gunicorn ps.redis pkg ]);
in
{
  options.services.lorry = {
    enable = lib.mkEnableOption "lorry";

    enablePostgres = lib.mkEnableOption "automatic postgres setup";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./. { };
    };

    hostname = lib.mkOption {
      type = lib.types.str;
      description = "hostname lorry will run from";
      example = "lorry.example.com";
    };

    resourcesPath = lib.mkOption {
      type = lib.types.path;
      description = "path the uploads are stored at";
      default = "/var/lib/lorry/resources";
    };

    extraConfig = lib.mkOption {
      type = lib.types.str;
      description = "extra configuration (Python)";
      default = "";
    };

    configFilePath = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      description = "path to a file with extra configuration";
      default = null;
    };

    socket = lib.mkOption {
      type = lib.types.path;
      description = "path to the gunicorn listen socket";
      default = "/run/lorry.sock";
    };

    workerCount = lib.mkOption {
      type = lib.types.int;
      description = "gunicorn worker count";
      default = 4;
    };
  };

  config = lib.mkIf cfg.enable {
    users.users.${user} = {
      inherit group;
      isSystemUser = true;
    };
    users.groups.${group} = {};

    systemd.tmpfiles.rules = [
      "d ${cfg.resourcesPath} 0750 ${user} ${group} - -"
    ];

    systemd.services.lorry = {
      description = "Lorry gunicorn server";
      serviceConfig = {
        Type = "notify";
        NotifyAccess = "main";
        ExecStart = "${pythonEnv}/bin/gunicorn --workers ${builtins.toString cfg.workerCount} -m 007 lorryserver.app:app";
        User = user;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ReadWritePaths = cfg.resourcesPath;
      };
    };
    systemd.sockets.lorry = {
      description = "Lorry listen socket";
      wantedBy = [ "sockets.target" ];
      socketConfig = {
        ListenStream = cfg.socket;
        SocketUser = user;
        SocketGroup = webserver.group;
        SocketMode = 0660;
      };
    };

    services.caddy.enable = true;
    services.caddy.virtualHosts.${cfg.hostname}.extraConfig = ''
      reverse_proxy unix/${cfg.socket}
    '';

    services.redis.servers.lorry = {
      enable = true;
      user = user;
      group = user;
    };

    services.postgresql = lib.mkIf cfg.enablePostgres {
      enable = true;
      ensureUsers = [{
        name = user;
        ensureDBOwnership = true;
      }];
      ensureDatabases = [ user ];
    };

    systemd.services.lorry-initdb = lib.mkIf cfg.enablePostgres {
      description = "init lorry database";
      wantedBy = [ "multi-user.target" ];
      after = [ "postgresql.service" ];
      before = [ "lorry.service" ];
      script = ''
        ${pythonEnv}/bin/python3 -c "from lorryserver.db.init_database import init_database;init_database()"
      '';
      serviceConfig.User = user;
    };

  };
}

