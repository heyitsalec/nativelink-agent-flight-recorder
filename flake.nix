{
  description = "NativeLink Agent Flight Recorder dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    nativelink.url = "github:TraceMachina/nativelink";
  };

  outputs = {
    self,
    nixpkgs,
    nativelink,
  }: let
    systems = [
      "aarch64-darwin"
      "aarch64-linux"
      "x86_64-darwin"
      "x86_64-linux"
    ];
    forAllSystems = nixpkgs.lib.genAttrs systems;
  in {
    devShells = forAllSystems (system: let
      pkgs = import nixpkgs {inherit system;};
      nativelinkPkg = nativelink.packages.${system}.default;
      bazelShim = pkgs.writeShellScriptBin "bazel" ''
        unset TMPDIR TMP
        exec ${pkgs.bazelisk}/bin/bazelisk "$@"
      '';
    in {
      default = pkgs.mkShell {
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
          echo "NLFR dev shell: nativelink=$NLFR_NATIVELINK_BIN bazel=$NLFR_BAZEL_BIN"
        '';
      };
    });
  };
}
