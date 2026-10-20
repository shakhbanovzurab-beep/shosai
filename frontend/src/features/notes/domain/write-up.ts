/** Вид раздела записи Leo, как его пишет сервер. */
export type WriteUpKind = "summary" | "key_points" | "decisions" | "action_items";

/** Находка из записи Leo с её доказательством во встрече. */
export interface WriteUpFinding {
  id: string;
  text: string;
  ownerName: string | null;
  /** Срок в ISO-дате, если встреча его назвала. */
  dueOn: string | null;
  /** С какой миллисекунды встречи начинается доказательство. */
  startMs: number;
}

/** Раздел записи, уже разложенный сервером по шаблону. */
export interface WriteUpSection {
  kind: WriteUpKind;
  /** Код заголовка встроенного шаблона; кабинет называет его на языке человека. */
  headingCode: string | null;
  /** Своё название раздела из шаблона человека. */
  title: string | null;
  /** Текст сводки; у разделов-списков — null. */
  text: string | null;
  items: WriteUpFinding[] | null;
}

/** Запись Leo о встрече: по какому шаблону, писал ли её Leo сам и её разделы. */
export interface WriteUp {
  templateId: string;
  automatic: boolean;
  revision: number;
  sections: WriteUpSection[];
}
