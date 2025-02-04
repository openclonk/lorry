{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";

  outputs = { self, nixpkgs, flake-utils }:
    (flake-utils.lib.eachDefaultSystem
      (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
        in
        {
          packages.default = pkgs.callPackage ./. { };
          devShells.default = pkgs.mkShell {
            inputsFrom = [
              self.packages.${system}.default
            ];
          };
        })
    ) // {
      nixosModules.default = import ./module.nix;
      # Container for testing
      nixosConfigurations.container = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          self.nixosModules.default
          ({ pkgs, ... }: {
            boot.isContainer = true;
            networking.firewall.allowedTCPPorts = [ 80 ];

            services.lorry = {
              enable = true;
              enablePostgres = true;
              hostname = ":80";
              extraConfig = ''
                DEBUG = True
                SECRET_KEY = b'testsecret'
                SSO_ENDPOINT = None
              '';
            };

          })
        ];
      };
    };
}
