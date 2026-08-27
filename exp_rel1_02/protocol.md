# EXP-GM-REL1-02 protocol

REL1-v2 is a fresh-surface regression for the three frozen REL1 action items.
It keeps history private to TrustUpdater and current reports identical across
control/intervention. Formation counts source-correct history rows; update uses
only the final row because `latest_is_binding=true`.

TrustUpdater must cite row IDs and receives no privileged source ordering.
The Dispatcher returns only a registered business value. The platform binds
that choice to the actually delivered and adopted trust message, adding the
registered action name, real message ID, current trust version, and round.

The formal matrix is three new tasks by two variants, one full workflow track,
seed 0: 6 cells and 30 calls. Drop/no-history and illegal binding behavior are
covered by deterministic TrustLedger tests. The frozen EXP-GM-REL1 result is
not rescored.
