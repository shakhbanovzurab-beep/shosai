import type { Currency } from "../domain/contract";
import type { Random } from "./random";

/* Customer names and billing emails for the demo: people on Pro, companies on Team and Enterprise. */

/** "Иван:ivan Анна:anna" → [["Иван", "ivan"], ["Анна", "anna"]] */
const pairs = (list: string) => list.split(" ").map((entry) => entry.split(":") as [string, string]);

const MALE = pairs(
  "Алексей:aleksey Дмитрий:dmitry Иван:ivan Михаил:mikhail Сергей:sergey Андрей:andrey Артём:artem Никита:nikita Павел:pavel Егор:egor Кирилл:kirill Роман:roman",
);
const FEMALE = pairs(
  "Анна:anna Мария:maria Екатерина:ekaterina Ольга:olga Наталья:natalya Елена:elena Дарья:darya Ксения:ksenia Алина:alina Виктория:viktoria Полина:polina Юлия:yulia",
);
/** Surnames whose feminine form adds "а". */
const SURNAMES = pairs(
  "Иванов:ivanov Смирнов:smirnov Кузнецов:kuznetsov Попов:popov Соколов:sokolov Лебедев:lebedev Козлов:kozlov Новиков:novikov Морозов:morozov Волков:volkov Соловьёв:solovyov Васильев:vasilyev Зайцев:zaytsev Павлов:pavlov Семёнов:semenov Голубев:golubev Виноградов:vinogradov Богданов:bogdanov Орлов:orlov Фёдоров:fedorov",
);
const COMPANY_HEADS = pairs(
  "Норд:nord Волга:volga Урал:ural Север:sever Байкал:baikal Алтай:altai Нева:neva Кама:kama Амур:amur Сибирь:sibir Вектор:vector Гранит:granit Квант:kvant Меридиан:meridian Орбита:orbita Пульс:puls",
);
const COMPANY_TAILS = pairs(
  "Софт:soft Тех:tech Лаб:lab Дата:data Логистик:logistic Медиа:media Финанс:finance Строй:stroy Консалт:consult Трейд:trade Фарм:pharm Агро:agro",
);

const MAIL_DOMAINS: Record<Currency, string[]> = {
  RUB: ["yandex.ru", "gmail.com", "mail.ru", "ya.ru", "inbox.ru"],
  USD: ["gmail.com", "outlook.com", "icloud.com", "proton.me"],
  EUR: ["gmail.com", "outlook.com", "proton.me", "gmx.de"],
};

/** Legal form and top-level domain by the currency a company pays in. */
const COMPANY_STYLE: Record<Currency, { name: (brand: string, latin: string) => string; tld: string }> = {
  RUB: { name: (brand) => `ООО «${brand}»`, tld: "ru" },
  USD: { name: (_, latin) => `${latin} Inc.`, tld: "com" },
  EUR: { name: (_, latin) => `${latin} GmbH`, tld: "eu" },
};

const capitalize = (value: string) => `${value[0].toUpperCase()}${value.slice(1)}`;

export function createPeople(random: Random) {
  const usedEmails = new Set<string>();
  const usedCompanies = new Set<string>();

  const uniqueEmail = (local: string, domain: string) => {
    let email = `${local}@${domain}`;
    for (let n = 2; usedEmails.has(email); n++) email = `${local}${n}@${domain}`;
    usedEmails.add(email);
    return email;
  };

  return {
    person(currency: Currency) {
      const female = random.chance(0.48);
      const [first, firstLat] = random.pick(female ? FEMALE : MALE);
      const [last, lastLat] = random.pick(SURNAMES);
      return {
        name: `${first} ${female ? `${last}а` : last}`,
        email: uniqueEmail(`${firstLat}.${lastLat}${female ? "a" : ""}`, random.pick(MAIL_DOMAINS[currency])),
      };
    },

    company(currency: Currency) {
      let brand = "";
      let latin = "";
      for (let attempt = 0; attempt < 20 && (brand === "" || usedCompanies.has(brand)); attempt++) {
        const [head, headLat] = random.pick(COMPANY_HEADS);
        const [tail, tailLat] = random.pick(COMPANY_TAILS);
        brand = `${head}${tail.toLowerCase()}`;
        latin = `${capitalize(headLat)}${tailLat}`;
      }
      if (usedCompanies.has(brand)) {
        brand = `${brand} ${usedCompanies.size}`;
        latin = `${latin}${usedCompanies.size}`;
      }
      usedCompanies.add(brand);
      const style = COMPANY_STYLE[currency];
      return {
        name: style.name(brand, latin),
        email: uniqueEmail("billing", `${latin.toLowerCase()}.${style.tld}`),
      };
    },
  };
}
