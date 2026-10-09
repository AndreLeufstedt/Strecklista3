# Legacy Database Directory

Placera den gamla SQLite-databasfilen (`streck.db`) i denna mapp.

När databasen ligger här kan datamigrering genomföras genom att köra:
```bash
make migrate
```

Obs: `make migrate` kan endast köras om den nya databasen är helt tom.
Om du vill återställa den nya databasen till tomt fabriksläge, kör:
```bash
make reset
```
