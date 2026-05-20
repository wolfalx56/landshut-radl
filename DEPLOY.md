# Deploy auf M1server (192.168.178.50)

## Einmalig: Projekt übertragen

```bash
# Von deinem Mac aus:
rsync -av --exclude='node_modules' --exclude='data/cache' \
  /Users/alexanderwolf/landshut-radl/ \
  alex@192.168.178.50:~/landshut-radl/
```

## Starten

```bash
ssh alex@192.168.178.50
cd ~/landshut-radl
docker compose up --build -d
```

Build dauert beim ersten Mal ~3-5 Minuten (Node + Python Dependencies).

## App öffnen

- Zuhause: http://192.168.178.50:8080
- Unterwegs via WireGuard: gleiche URL

## iPhone: Als App installieren

1. Safari öffnen → http://192.168.178.50:8080
2. Teilen-Button → "Zum Home-Bildschirm"
3. Fertig — Icon erscheint wie eine App

## Icons generieren (einmalig auf Server)

```bash
cd ~/landshut-radl/frontend/public
sudo apt install -y librsvg2-bin
bash generate-icons.sh
# Danach neu bauen:
cd ~/landshut-radl && docker compose up --build -d
```

## Logs

```bash
docker compose logs -f
```

## Update nach Code-Änderungen

```bash
rsync -av --exclude='node_modules' --exclude='data/cache' \
  /Users/alexanderwolf/landshut-radl/ \
  alex@192.168.178.50:~/landshut-radl/
ssh alex@192.168.178.50 "cd ~/landshut-radl && docker compose up --build -d"
```
