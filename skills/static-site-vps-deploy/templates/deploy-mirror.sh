#!/usr/bin/env bash
# Mirror a static site from this repo to a VPS behind nginx.
# tar runs on the client (Git Bash has no rsync); rsync --delete runs on the
# server (where it exists), so files deleted locally disappear from the air.
set -euo pipefail

SERVIDOR="root@<VPS_IP>"
DESTINO="/var/www/<docroot>"
SITE="https://<domain>"

echo "Enviando arquivos para $SERVIDOR ..."
tar -czf - \
    --exclude=src-projeto --exclude=node_modules --exclude=.git \
    --exclude=_offline --exclude=deploy.sh --exclude=README.md \
    --exclude=.gitignore . \
  | ssh "$SERVIDOR" "
      set -e
      rm -rf /tmp/site-stage && mkdir -p /tmp/site-stage
      tar -xzf - -C /tmp/site-stage
      rsync -a --delete /tmp/site-stage/ $DESTINO/
      chown -R www-data:www-data $DESTINO
      rm -rf /tmp/site-stage
    "

echo
echo "Conferindo o que subiu:"
# || true: Git Bash curl prints the right code but exits 23 writing to
# /dev/null, and set -e would kill the check exactly when it passed.
codigo() { curl -s -o /dev/null -w "%{http_code}" --max-time 25 "$1" || true; }

falhou=0
# Pages that must be up.
for pagina in \
  "$SITE/<path>/" \
  "$SITE/"
do
  http=$(codigo "$pagina")
  [ "$http" = "200" ] || falhou=1
  printf '  %s  %s\n' "$http" "$pagina"
done

# Routes that must be DEAD (removed pages, old duplicated paths).
for morta in \
  "$SITE/<removed-path>/index.html"
do
  http=$(codigo "$morta")
  [ "$http" = "404" ] || falhou=1
  printf '  %s  %s  (esperado 404)\n' "$http" "$morta"
done

echo
if [ "$falhou" -eq 0 ]; then
  echo "Tudo no ar: $SITE/"
else
  echo "ALGO NAO RESPONDEU O ESPERADO — confira a lista acima."
  exit 1
fi
