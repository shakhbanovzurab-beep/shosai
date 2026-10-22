# Glossary: Turkish (tr)

Address the user as siz. Buttons and menu items use the bare imperative (Kaydet, Dosya ekle), never -(y)InIz, -mAk or lütfen; hints and messages use the -(y)In form (Tekrar deneyin).
Errors name what failed with a passive -AmAdI verb, then the fix: “Kaydedilemedi. Bağlantınızı kontrol edin.” Empty states: “Henüz dosya yok” + “Başlamak için bir dosya yükleyin.” Never Hata!, Hay aksi or başarısız oldu.
After a number the noun stays singular (3 dosya, {count} token), so ICU one and other usually read the same; never add -lAr in code.
Suffixes after names and codes take ’ and follow pronunciation (Leo’ya, Notion’a, MCP’ye); never attach a suffix to a {placeholder}, rephrase instead (“{name} silinsin mi?”). Case with Turkish rules: i/İ, ı/I.

## Terms

| English | Use | Avoid | Note |
| --- | --- | --- | --- |
| Personal | Kişisel | şahsi | Space switcher label, the opposite of a çalışma alanı. |
| workspace | çalışma alanı | çalışma ortamı | Always in full: çalışma alanına, çalışma alanınız. |
| Hub | Merkezler | — | Section label, plural like Toplantılar. |
| hub | merkez | — | One deal, project or hire with its meetings, tasks and files: merkezi, merkeze. |
| Productivity | Verimlilik | üretkenlik, prodüktivite | Home section. |
| Inbox | Gelen kutusu | inbox, gelen postalar, e-mail | Sidebar item Email = E-posta. |
| Meetings | Toplantılar | miting | |
| Calendar | Takvim | ajanda | |
| Kanban | Kanban | — | Method name, not translated; the boards in it are pano. |
| Notes | Notlar | — | |
| File Manager | Dosya yöneticisi | dosya gezgini | Sentence case. |
| Knowledge | Bilgi bankası | bilgi tabanı, malumat | Also knowledge base; workspace knowledge = çalışma alanı bilgileri. |
| Settings | Ayarlar | konfigürasyon | Path: Ayarlar › Leo. |
| Support | Destek | bilet | Support tickets = destek talepleri. |
| Upgrade plan | Planı yükselt | upgrade, planı güncelle | Yükselt alone where space is tight. |
| Download the app | Uygulamayı indir | karşıdan, download | Install = yükle. |
| task | görev | vazife | görevi, görevler. |
| board | pano | tahta | panoya, panolar. |
| column | sütun | kolon | |
| project | proje | — | |
| decision | karar | — | |
| agreement | taahhüt | mutabakat | A promise made in a meeting: taahhüdü, taahhütler. Not anlaşma, which is a sales deal. |
| action item | takip görevi | aksiyon, eylem maddesi, eylem öğesi | Plural takip görevleri. |
| due date | son tarih | teslim tarihi, vade tarihi, deadline | On invoices: son ödeme tarihi. |
| owner | sahip | malik | Label Sahip; in a sentence dosyanın sahibi. Same word as the access role. |
| task owner | sorumlu |  | Tasks and hub topics; the owner of a file or workspace keeps the owner word |
| lead | lider |  | Label form: “Lider: {name}” |
| assignee | atanan kişi | atanmış, sorumlu kişi, görevlendirilen | Assigned to me = Bana atanan görevler. |
| priority | öncelik | önem derecesi | Values Yüksek, Orta, Düşük. |
| status | durum | statü | |
| template | şablon | kalıp, template | |
| automation | otomasyon | — | |
| field | alan | sticker, çıkartma | alanı, alanlar; Pano alanları, Yeni alan; built-in ones are hazır alanlar. In code and the API a sticker |
| state | seçenek | — | seçeneği, seçenekler; one choice of a field’s set of states. Not durum, which is status |
| stopwatch | kronometre | — | kronometresi |
| timer | zamanlayıcı | — | zamanlayıcısı |
| time tracking | zaman takibi | — | plan and fact |
| subtask | alt görev | — | alt görevi, alt görevler; Alt görev ekle |
| comment | yorum | — | yorumu, yorumlar |
| cover | kapak | — | Kapak yap, Kapağı kaldır |
| repeat | tekrarlama | — | Field label Tekrarlama; values Hiçbir zaman, Her gün, Her hafta, Her ay; a repeating task is tekrarlanan görev |
| overdue | gecikti | — | Label Gecikti; as an adjective gecikmiş görev |
| meeting | toplantı | miting | Covers calls and in-person meetings. |
| recording | kayıt | — | kaydı, kayda, kayıtlar. |
| transcript | transkript | deşifre, döküm, transkripsiyon | transkripti, transkripte. |
| transcribing | Transkript oluşturuluyor… | transkribe, yazıya dök | Progress label; when finished: Transkript hazır. |
| summary | özet | hülasa | |
| key points | önemli noktalar | kilit nokta, anahtar nokta, ana noktalar | |
| mind map | zihin haritası | akıl haritası, mind map | |
| participant | katılımcı | iştirakçi | |
| file | dosya | evrak | |
| folder | klasör | — | Default name: Adsız klasör. |
| starred | yıldızlı | favori, yıldızlanmış | Actions: Yıldız ekle, Yıldızı kaldır. |
| shared | paylaşılan | paylaşımlı | Shared with me = Benimle paylaşılanlar. |
| trash | çöp kutusu | çöp sepeti, geri dönüşüm | Move to trash = Çöp kutusuna taşı. |
| upload | Yükle | karşıya, upload | Noun yükleme. Yükleniyor… also means Loading…, so buttons say Dosya yükle. |
| share link | paylaşım bağlantısı | link | bağlantı also means a network connection; context tells them apart. |
| document | belge | doküman, döküman | |
| source | kaynak | — | kaynağı, kaynaklar. |
| connector | bağlayıcı | konnektör, connector | |
| sync | Senkronize et | eşitle, eşzamanla, sync | Noun senkronizasyon; Syncing… = Senkronize ediliyor… |
| index / indexing | Dizine ekle | indeks, endeks | Noun dizin; Indexing… = Dizine ekleniyor…; Indexed = Dizine eklendi. |
| context | bağlam | kontekst | |
| prompt | istem | prompt | Plural istemler. |
| system message | sistem mesajı | sistem istemi, sistem iletisi | |
| skill | beceri | yetenek | Plural beceriler. For model capabilities use özellikler. |
| model | model | — | Model names stay as written. |
| role | rol | — | A job Leo does: rolü, rolde. Same word as the access role. |
| temperature | sıcaklık | temperatür | |
| max tokens | maksimum token | max token, maks. token | |
| reasoning | akıl yürütme | muhakeme, mantık yürütme | |
| token | token | belirteç, jeton | Singular after numbers: {count} token. Prefer token sayısı over case endings. |
| frontier models | en gelişmiş modeller | frontier, sınır modeli, öncü model | |
| account | hesap | — | hesabı, hesabınız. |
| profile | profil | — | |
| privacy | gizlilik | mahremiyet | |
| billing | faturalandırma | faturalama | |
| plan | plan | tarife | |
| subscription | abonelik | abonman | |
| seat | lisans | koltuk | Price per seat: kullanıcı başına. |
| invoice | fatura | — | |
| payment method | ödeme yöntemi | ödeme şekli, ödeme metodu | |
| usage | kullanım | sarfiyat, tüketim | |
| limit | sınır | limit | sınırı, sınıra; unlimited = sınırsız. |
| memory | bellek | hafıza | |
| custom instructions | özel talimatlar | özel yönerge, özelleştirilmiş talimat | |
| MCP server | MCP sunucusu | mcp server | Plural MCP sunucuları. |
| tool | araç | tool | araçlar. |
| member | üye | — | |
| team | ekip | takım | |
| invitation | davet | davetiye | |
| role (access) | rol | konuk, admin | Values sahip, yönetici, üye, misafir. |
| chat | sohbet | — | sohbeti, sohbetler. |
| message | mesaj | iletiyi, iletiler | Chat and mail alike; Gmail’s ileti is not used. |
| new chat | Yeni sohbet | yeni konuşma | |
| voice mode | sesli mod | ses modu, konuşma modu | |
| attach / attachment | Dosya ekle / ek | iliştir, eklenti | Plural ekler. |
| regenerate | Yeniden oluştur | yeniden üret, tekrar üret | |
| suggestions | öneriler | tavsiye | |
| needs approval | Onay gerekiyor | onay bekliyor, onay lazım | Button Onayla; what Leo waits to run is an işlem. |
| thread | yazışma | ileti dizisi, thread, zincir | Plural yazışmalar. |
| reply / reply all / forward | Yanıtla / Tümünü yanıtla / Yönlendir | cevap, herkese yanıt, herkesi yanıtla | Leo’s answers are yanıt too. |
| draft | taslak | müsvedde | |
| archive | Arşivle | arşive taşı, arşive kaldır | Noun arşiv. |
| label | etiket | — | |
| Save | Kaydet | muhafaza | |
| Cancel | İptal | vazgeç | With an object: Aboneliği iptal et. |
| Done | Bitti | — | OK = Tamam; a finished task is Tamamlandı. |
| Create | Oluştur | yaratıldı | |
| Add | Ekle | ilave | |
| Edit | Düzenle | editle | |
| Rename… | Yeniden adlandır… | ismini değiştir, adını değiştir | Keep the …, it opens a dialog. |
| Duplicate | Kopyasını oluştur | çoğalt, klonla | Name of the copy: {name} kopyası. |
| Delete | Sil | imha | Delete forever = Kalıcı olarak sil. |
| Remove | Kaldır | — | Never Sil here: nothing is destroyed. |
| Restore | Geri yükle | eski haline, restore | |
| Undo | Geri al | — | |
| Retry / Try again | Tekrar dene | yeniden dene | In a sentence: Tekrar deneyin. |
| Close | Kapat | — | |
| Copy link | Bağlantıyı kopyala | — | |
| Search | Ara | — | Field placeholder Ara…; noun arama. |
| Filter | Filtrele | süzgeç | Noun filtre. |
| Sort | Sırala | — | Sort by = Sıralama ölçütü. |
| Connect / Disconnect | Bağla / Bağlantıyı kes | bağlantıyı kopar | Status Bağlı. |
| Log out | Çıkış yap | oturumu kapat, log out | Log in = Giriş yap. |
| Manage | Yönet | idare et | |
| Couldn’t … | … -AmAdI on the passive verb: Kaydedilemedi, Dosyalar yüklenemedi | başarısız oldu, hata oluştu, hay aksi | Then the fix in siz: Bağlantınızı kontrol edin. |
| No … yet | Henüz … yok | bulunmamaktadır | Singular noun: Henüz dosya yok. |
| Saving… / Loading… | Kaydediliyor… / Yükleniyor… | kaydedilmekte, yüklenmekte | Passive -iyor plus the … character. |
| … copied | … kopyalandı | kopyalanmıştır | Bağlantı kopyalandı. Don’t mention the clipboard: pano is the board. |

## Same as English

- `Kanban`
- `Model`
- `Plan`
- `Token`
- `Video`
