import { CreditCard } from "lucide-react";
import {
  type SimpleIcon as Brand,
  siAmericanexpress,
  siDinersclub,
  siDiscover,
  siJcb,
  siMastercard,
  siVisa,
} from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";
import type { CardBrand } from "@/lib/card-brand";

// simple-icons has no UnionPay or Mir mark; those and unknown cards fall back to a generic card.
const LOGOS: Partial<Record<CardBrand, Brand>> = {
  visa: siVisa,
  mastercard: siMastercard,
  amex: siAmericanexpress,
  discover: siDiscover,
  jcb: siJcb,
  diners: siDinersclub,
};

/** The card network's mark on a dark tile, like a wallet; decorative, the name is written next to it. */
export function CardBrandIcon({ brand }: { brand: CardBrand }) {
  const logo = LOGOS[brand];
  return (
    <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-zinc-900 text-white" aria-hidden="true">
      {logo ? (
        <SimpleIcon icon={logo} className="size-6 fill-current" aria-hidden="true" />
      ) : (
        <CreditCard className="size-5" />
      )}
    </span>
  );
}
