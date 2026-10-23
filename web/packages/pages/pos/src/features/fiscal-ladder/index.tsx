/**
 * «Kassa 46 soatdan beri ...» (16 §6, qaror #43; 07 "Offline fiskal shkala"): at `modal46` every new fiscal
 * document (sale, return with a money part) first shows this modal; it closes only with «Tushundim».
 * Shared by POS-02 and POS-05 (review UX-07).
 */
import { useTranslation } from "@shared/i18n";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@shared/ui";

/** Does a new fiscal document need the 46 h acknowledgement first? */
export const needsLadder46 = (level: string, fiscalDocument: boolean, acknowledged: boolean): boolean =>
  level === "modal46" && fiscalDocument && !acknowledged;

export function Ladder46Modal({ onOk }: { onOk: () => void }) {
  const { t } = useTranslation("pos");
  return (
    <Dialog open onOpenChange={(o) => !o && onOk()}>
      <DialogContent size="sm" hideClose data-testid="ladder-46-modal">
        <DialogHeader>
          <DialogTitle>{t("fiscalLadder.modalTitle")}</DialogTitle>
          <DialogDescription>{t("fiscalLadder.modalText")}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button size="pos" autoFocus onClick={onOk} data-testid="ladder-46-ok">
            {t("fiscalLadder.modalOk")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
