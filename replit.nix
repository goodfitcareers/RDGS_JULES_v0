{ pkgs }: {
  deps = [
    pkgs.python311
    pkgs.poetry
    pkgs.nodejs_20
    pkgs.postgresql_15
    pkgs.openssl
  ];
}
