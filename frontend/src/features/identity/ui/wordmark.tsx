import { ShosaiMark } from "@/components/shosai-mark";
import { ShosaiName } from "@/components/shosai-name";

/** Знак Shosai на страницах входа: логотип 32 px и название с заглавными 20 px в одну компактную строку. */
export function Wordmark() {
  return (
    <div className="flex items-center gap-2.5">
      <ShosaiMark className="size-8" />
      <ShosaiName capHeight={20} />
    </div>
  );
}
