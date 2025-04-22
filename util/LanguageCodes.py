## 5/25/21: Cannibalized from NezukoBox (Demon Slayer) and repurposed for TextBridge


class Language:
    ## Languages
    Japanese = "ja"
    English = "en"
    French = "fr"
    Italian = "it"
    German = "de"
    Spanish = "es"
    Russian = "ru"
    Polish = "pl"
    Arabic = "ar"
    Portuguese = "pt"
    ChineseTrad = "zh"
    ChineseSimp = "zhs"
    Korean = "ko"

    ### Lists
    FIGScodes = [French, Italian, German, Spanish]
    EFIGScodes = [English, French, Italian, German, Spanish]
    JEFIGScodes = [Japanese, English, French, Italian, German, Spanish]
    AllLangCodes = [Japanese, English, French, Italian, German,
                    Spanish, Russian, Polish,
                    Arabic, Portuguese, ChineseTrad, ChineseSimp, Korean]

    ## Dicts
    textbridge_to_xliff = {"US_English":"en",
                           "JP_Japanese":"ja",
                           "EU_French":"fr",
                           "EU_Italian":"it",
                           "EU_German":"de",
                           "EU_Spanish":"es"}
    xliff_to_textbridge = {v: k for k, v in textbridge_to_xliff.items()}
