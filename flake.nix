{
  description = "NativeLink Agent Flight Recorder dev environment";

  inputs = {
    flake-parts = {
      follows = "nativelink/flake-parts";
    };
    nativelink = {
      url = "github:TraceMachina/nativelink/946fd0d0ae46bfc2f2df2c4b63da5565cb6b03b4";
    };
    nixpkgs = {
      follows = "nativelink/nixpkgs";
    };
    rust-overlay = {
      follows = "nativelink/rust-overlay";
    };
  };

  outputs = inputs @ {
    flake-parts,
    nativelink,
    nixpkgs,
    rust-overlay,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-darwin"
        "x86_64-linux"
      ];

      imports = [
        nativelink.flakeModules.lre
      ];

      perSystem = {
        config,
        pkgs,
        system,
        ...
      }: let
        nativelinkPkg = nativelink.packages.${system}.default;
        bazelShim = pkgs.writeShellScriptBin "bazel" ''
          unset TMPDIR TMP
          exec ${pkgs.bazelisk}/bin/bazelisk "$@"
        '';
      in {
        _module.args.pkgs = import nixpkgs {
          inherit system;
          overlays = [
            nativelink.overlays.lre
            rust-overlay.overlays.default
          ];
        };

        lre = {
          Env = with pkgs.lre;
            if pkgs.stdenv.isDarwin
            then lre-rs.meta.Env
            else (lre-cc.meta.Env ++ lre-rs.meta.Env);
          prefix = "lre";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.bashInteractive
            pkgs.coreutils
            pkgs.curl
            pkgs.git
            pkgs.jq
            pkgs.nodejs_22
            pkgs.python313
            pkgs.uv
            pkgs.bazelisk
            bazelShim
            nativelinkPkg
          ];

          shellHook = ''
            export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
            export NLFR_NATIVELINK_BIN="${nativelinkPkg}/bin/nativelink"
            export NLFR_BAZEL_BIN="${bazelShim}/bin/bazel"
            export BAZELISK_HOME="$PWD/.cache/bazelisk"
            mkdir -p "$BAZELISK_HOME"
            ${config.lre.installationScript}
            echo "NLFR dev shell: nativelink=$NLFR_NATIVELINK_BIN bazel=$NLFR_BAZEL_BIN"
          '';
        };
      };
    };
}
