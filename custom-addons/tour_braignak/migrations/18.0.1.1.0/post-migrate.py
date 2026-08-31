# -*- coding: utf-8 -*-
"""Rendre le journal de Braignak inaltérable en pratique, pas seulement en théorie.

Le modèle refuse déjà toute modification/suppression via l'ORM. Mais deux
trous subsistaient au niveau de la BASE, et une promesse qui tient à l'ORM
mais pas à psql est une promesse qui ne tient pas :

1. La clé étrangère `braignak_journal_etude_id_fkey` était en
   `ON DELETE CASCADE` : supprimer une étude directement en SQL effaçait
   silencieusement son journal. On la repasse en `ON DELETE RESTRICT`.

2. Aucun verrou côté base n'empêchait `UPDATE`/`DELETE` sur la table.
   On pose un trigger qui refuse les deux, pour tout le monde, y compris en
   psql : le seul qui ne peut pas être contourné par une session SQL.

Le trigger et la contrainte sont idempotents (création conditionnelle).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'braignak_journal_etude_id_fkey'
                  AND conrelid = 'braignak_journal'::regclass
            ) THEN
                ALTER TABLE braignak_journal
                    DROP CONSTRAINT braignak_journal_etude_id_fkey;
            END IF;
        END $$;
    """)
    cr.execute("""
        ALTER TABLE braignak_journal
            ADD CONSTRAINT braignak_journal_etude_id_fkey
            FOREIGN KEY (etude_id) REFERENCES braignak_etude(id)
            ON DELETE RESTRICT;
    """)
    cr.execute("""
        CREATE OR REPLACE FUNCTION braignak_journal_verrou() RETURNS trigger
        AS $$
        BEGIN
            RAISE EXCEPTION
                'Journal de Braignak inaltérable : modification ou suppression interdite, y compris en SQL direct.';
        END;
        $$ LANGUAGE plpgsql;
    """)
    cr.execute("""
        DROP TRIGGER IF EXISTS braignak_journal_inalterable ON braignak_journal;
    """)
    cr.execute("""
        CREATE TRIGGER braignak_journal_inalterable
        BEFORE UPDATE OR DELETE ON braignak_journal
        FOR EACH ROW EXECUTE FUNCTION braignak_journal_verrou();
    """)
    _logger.info(
        "Braignak : journal verrouillé en base (RESTRICT + trigger inaltérable)")
