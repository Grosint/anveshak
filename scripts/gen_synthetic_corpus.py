"""Generate a synthetic corpus for development and UI work.

SYNTHETIC DATA. Every item this script writes is invented: the outlets, the
handles, the dates and the text. It exists so the workbench can be developed
and demonstrated to ourselves against a populated database, and so that the
detection path can be exercised end to end without waiting for a collection
run that reaches the public internet.

It is NOT the demonstration corpus. The demonstration corpus is collected by
``scripts/build_corpus.py`` against ``infra/configs/corpora/*.yaml``, and its
whole claim to an evaluating officer is that it fabricates no timestamp and
no outlet. Mixing the two would destroy that claim, so the output of this
script is written under a ``synthetic_`` file name, every item carries
``synthetic: true`` in its discovery label, and the file header says so in
the first line a reader sees.

The output is deterministic for a given ``--seed``, so the file is
reproducible from the script rather than being a blob nobody can regenerate.

Usage::

    uv run python scripts/gen_synthetic_corpus.py \\
        --out corpora/synthetic_cockroach_janta_party.jsonl --seed 54

Then import it into a Topic the ordinary way::

    POSTGRES_URL=... uv run python scripts/import_corpus.py \\
        corpora/synthetic_cockroach_janta_party.jsonl \\
        --topic-id <uuid> --org-id org-anshul
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

IST = timezone(timedelta(hours=5, minutes=30))

SUBJECT = "Cockroach Janta Party"
SHORT = "CJP"
BREAKAWAY = "Nav Cockroach Morcha"


# ── Outlets ────────────────────────────────────────────────────────────
#
# Every host is under a reserved example domain, so no real outlet is
# impersonated by a file that invents what an outlet published. Voices are
# what decide the copy: a wire item and a partisan blog item about one event
# are the same facts written by people with different obligations.


@dataclass(frozen=True)
class Outlet:
    handle: str
    name: str
    platform: str
    voice: str
    language: str
    host: str


OUTLETS: tuple[Outlet, ...] = (
    Outlet(
        "https://meridianwire.example.net/feed",
        "Meridian Wire",
        "web",
        "wire",
        "en",
        "meridianwire.example.net",
    ),
    Outlet(
        "https://globalpost.example.com/feed",
        "Global Post",
        "web",
        "wire",
        "en",
        "globalpost.example.com",
    ),
    Outlet(
        "https://dailyledger.example.in/feed",
        "The Daily Ledger",
        "web",
        "national",
        "en",
        "dailyledger.example.in",
    ),
    Outlet(
        "https://capitalherald.example.in/feed",
        "Capital Herald",
        "web",
        "national",
        "en",
        "capitalherald.example.in",
    ),
    Outlet(
        "https://samachar24.example.in/feed",
        "Samachar 24",
        "web",
        "hindi",
        "hi",
        "samachar24.example.in",
    ),
    Outlet(
        "https://rashtradarpan.example.in/feed",
        "Rashtra Darpan",
        "web",
        "hindi",
        "hi",
        "rashtradarpan.example.in",
    ),
    Outlet(
        "https://vidarbhatimes.example.in/feed",
        "Vidarbha Times",
        "web",
        "regional",
        "en",
        "vidarbhatimes.example.in",
    ),
    Outlet(
        "https://cjpvoice.example.org/feed",
        "CJP Voice",
        "web",
        "party",
        "en",
        "cjpvoice.example.org",
    ),
    Outlet(
        "https://truthstream.example.click/feed",
        "TruthStream Bharat",
        "web",
        "partisan",
        "en",
        "truthstream.example.click",
    ),
    Outlet(
        "https://janpulse.example.click/feed",
        "Jan Pulse Daily",
        "web",
        "partisan",
        "en",
        "janpulse.example.click",
    ),
    Outlet(
        "https://factcheckdesk.example.org/feed",
        "Fact Check Desk",
        "web",
        "factcheck",
        "en",
        "factcheckdesk.example.org",
    ),
    Outlet(
        "https://sanhitaopinion.example.in/feed",
        "Sanhita Opinion",
        "web",
        "opposing",
        "en",
        "sanhitaopinion.example.in",
    ),
    Outlet("@cjp_official", "CJP Official Channel", "telegram", "social_party", "en", "t.me"),
    Outlet("@cjp_yuva_morcha", "CJP Yuva Morcha", "telegram", "social_hindi", "hi", "t.me"),
    Outlet("@nagrik_manch", "Nagrik Manch", "twitter", "social_civic", "en", "x.example.com"),
    Outlet("@satire_adda", "Satire Adda", "twitter", "counter", "en", "x.example.com"),
)

BY_VOICE: dict[str, list[Outlet]] = {}
for _outlet in OUTLETS:
    BY_VOICE.setdefault(_outlet.voice, []).append(_outlet)


# ── Slot pools ─────────────────────────────────────────────────────────

SLOTS: dict[str, tuple[str, ...]] = {
    "city": ("Delhi", "Lucknow", "Patna", "Jaipur", "Bhopal", "Nagpur", "Ranchi", "Prayagraj"),
    "campus": (
        "the state university campus",
        "the polytechnic ground",
        "the district college quadrangle",
        "the aspirants' coaching hub",
        "the arts faculty lawn",
    ),
    "venue": (
        "Ramlila Maidan",
        "the collectorate gate",
        "the district library ground",
        "Gandhi Maidan",
        "the town hall steps",
    ),
    "spokesperson": (
        "a party convener",
        "the movement's student wing secretary",
        "a founding member",
        "the party's media coordinator",
    ),
    "official": (
        "a senior police officer",
        "the district magistrate",
        "a home department official",
        "the university registrar",
    ),
    "count_small": ("about 400", "roughly 700", "close to 1,200", "some 900"),
    "count_large": ("about 14,000", "close to 25,000", "roughly 40,000", "over 60,000"),
    "hi_city": ("दिल्ली", "लखनऊ", "पटना", "जयपुर", "भोपाल", "रांची"),
    "hi_venue": ("रामलीला मैदान", "कलेक्ट्रेट गेट", "गांधी मैदान", "टाउन हॉल"),
    "hi_count": ("करीब 800", "लगभग 2,000", "तकरीबन 5,000", "हज़ारों"),
}


@dataclass(frozen=True)
class Angle:
    """One event, written from several voices.

    ``lead`` is the sentence a reader scans, ``body`` the sentences that
    follow it. Both are drawn per item so that two outlets reporting one
    event produce different text without the difference being cosmetic.
    """

    slug: str
    voices: tuple[str, ...]
    lead: tuple[str, ...]
    body: tuple[str, ...]


@dataclass(frozen=True)
class Phase:
    number: int
    name: str
    start: date
    end: date
    angles: tuple[Angle, ...]
    items: int


# ── Phase 1: the founding ──────────────────────────────────────────────

P1 = (
    Angle(
        "cji-remark",
        ("wire", "national", "hindi", "social_civic"),
        (
            "A Chief Justice of India remark on student agitation has been read across campuses as a rebuke of the examination system.",
            "The Chief Justice's observation on repeated examination irregularities dominated campus discussion in {city} this week.",
            "मुख्य न्यायाधीश की टिप्पणी के बाद {hi_city} के छात्रों में परीक्षा प्रणाली को लेकर बहस तेज़ हो गई है।",
        ),
        (
            "Student bodies in {city} said the observation confirmed what aspirants have argued for two years.",
            "Coaching centres reported an unusually large turnout at evening discussion groups.",
            "{official} said no permission had been sought for any gathering.",
            "छात्र संगठनों ने कहा कि यह टिप्पणी उनकी लंबे समय से चली आ रही शिकायत की पुष्टि करती है।",
        ),
    ),
    Angle(
        "founding",
        ("wire", "national", "hindi", "party", "regional", "social_party"),
        (
            f"A new outfit calling itself the {SUBJECT} was founded at a public meeting in {{city}} on Saturday.",
            f"The {SUBJECT} was registered as a political formation a day after the Chief Justice's remark.",
            f"{SUBJECT} ने {{hi_city}} में एक सार्वजनिक बैठक में अपनी स्थापना की घोषणा की।",
            f"{{count_small}} people attended the founding meeting of the {SUBJECT} at {{campus}}.",
        ),
        (
            "{spokesperson} said the formation would contest examination irregularities rather than elections in its first year.",
            "The meeting adopted a four point charter on examination integrity, recruitment calendars and hostel fees.",
            "Organisers said chapters would be opened in seven districts by the end of the month.",
            "{official} confirmed that the meeting had informed the local police station in advance.",
            "बैठक में परीक्षा पारदर्शिता और भर्ती कैलेंडर पर चार सूत्री मांग पत्र पारित किया गया।",
        ),
    ),
    Angle(
        "first-press",
        ("national", "party", "partisan", "hindi"),
        (
            f"At its first press conference the {SUBJECT} said it would publish a district level register of delayed recruitment results.",
            f"The {SHORT} leadership rejected suggestions that it was backed by any existing party.",
            f"{SHORT} की पहली प्रेस वार्ता में भर्ती परिणामों में देरी का ज़िलावार रजिस्टर जारी करने की घोषणा की गई।",
        ),
        (
            "{spokesperson} said the register would be open to correction by any aspirant.",
            "Reporters were told the outfit had no paid office bearers.",
            "The claim of independence was not accompanied by an audited account of funding.",
            "प्रवक्ता ने कहा कि संगठन का कोई वेतनभोगी पदाधिकारी नहीं है।",
        ),
    ),
    Angle(
        "campus-chapters",
        ("regional", "national", "social_party", "party"),
        (
            f"{SHORT} chapters were announced at {{campus}} and two neighbouring institutions.",
            f"Students at {{campus}} in {{city}} said they had joined the {SHORT} reading circle this week.",
        ),
        (
            "Each chapter is to send one representative to a monthly coordination meeting.",
            "The university administration said no permission had been sought for a campus unit.",
            "{count_small} students signed the charter at the first reading circle.",
        ),
    ),
    Angle(
        "early-scepticism",
        ("opposing", "counter", "national"),
        (
            f"The {SUBJECT} is the fourth aspirant outfit launched in {{city}} in two years, and the previous three are dormant.",
            f"Whether the {SHORT} is a movement or a launch vehicle for its founders is the question nobody at its press conference asked.",
        ),
        (
            "Its charter repeats demands that two existing student unions already publish.",
            "The outfit has no published accounts, no membership audit, and a great deal of confidence.",
            "That is not a criticism of the grievance, which is real, but of the claim to represent it.",
        ),
    ),
)


# ── Phase 2: online growth, and the account block ──────────────────────

P2 = (
    Angle(
        "membership-claim",
        ("party", "partisan", "social_party", "social_hindi"),
        (
            f"The {SHORT} says it has crossed one hundred campus chapters in under six weeks.",
            f"{SHORT} membership has passed {{count_large}} according to figures circulated by the party's own channel.",
            f"{SHORT} का दावा है कि छह हफ़्ते में सौ से अधिक कैंपस इकाइयां बन चुकी हैं।",
        ),
        (
            "No verification of the figure is offered beyond the party's own count.",
            "The same number was posted by four accounts within an hour.",
            "Organisers say a district wise breakdown will follow.",
            "यह आंकड़ा संगठन के अपने चैनल से जारी किया गया है।",
        ),
    ),
    Angle(
        "account-block",
        ("wire", "national", "hindi", "party", "social_civic"),
        (
            f"The {SHORT}'s primary social account was withheld in India on Tuesday, the platform citing a legal request.",
            f"{SHORT} ने कहा कि उसका मुख्य सोशल मीडिया अकाउंट भारत में रोक दिया गया है।",
            f"The block on the {SHORT} account was confirmed by the platform's transparency page, which does not name the requesting authority.",
        ),
        (
            "{spokesperson} said the outfit had received no notice before the withholding.",
            "The account had about {count_large} followers at the time it was withheld.",
            "A home department official declined to confirm whether a request had been made.",
            "संगठन ने कहा कि उसे कोई पूर्व सूचना नहीं दी गई।",
        ),
    ),
    Angle(
        "mirror-accounts",
        ("social_party", "social_hindi", "partisan", "party"),
        (
            f"With the main handle withheld, {SHORT} updates moved to a mirror channel and a set of district groups.",
            f"मुख्य अकाउंट बंद होने के बाद {SHORT} की सूचनाएं मिरर चैनल और ज़िला समूहों पर दी जा रही हैं।",
        ),
        (
            "Subscribers were asked to forward posts rather than screenshot them.",
            "The mirror channel gained {count_small} subscribers in a day.",
            "समर्थकों से पोस्ट आगे भेजने के लिए कहा गया है।",
        ),
    ),
    Angle(
        "inflated-numbers-check",
        ("factcheck", "opposing", "national"),
        (
            f"A membership figure circulated by {SHORT} channels counts registrations rather than verified members, the outfit's own form shows.",
            f"The photograph shared as a {SHORT} rally in {{city}} is from an unrelated job fair in 2024, a reverse image search shows.",
        ),
        (
            "The registration form requires only a phone number and a district.",
            "The original photograph carries a watermark from a news agency that covered the job fair.",
            "The channels that posted it have not corrected the post.",
            "None of this settles whether the grievance is widespread, only what the number measures.",
        ),
    ),
    Angle(
        "column-growth",
        ("opposing", "national", "counter"),
        (
            f"The {SHORT} has discovered what every outfit before it discovered: outrage scales faster than organisation.",
            f"Six weeks of {SHORT} posts contain nine demands, four of which contradict the other five.",
        ),
        (
            "Its channels post more in a day than its charter says in total.",
            "Volume is not the same thing as support, and the outfit is banking on nobody noticing.",
            "A movement that cannot be audited is a movement that cannot be believed.",
        ),
    ),
)


# ── Phase 3: street mobilization ───────────────────────────────────────

P3 = (
    Angle(
        "march-announced",
        ("party", "social_party", "social_hindi", "national", "hindi"),
        (
            f"The {SHORT} has called a Sansad Chalo march to Parliament Street on 20 July.",
            f"{SHORT} ने 20 जुलाई को संसद चलो मार्च का ऐलान किया है।",
            f"Join us at {{venue}} on 20 July, the {SHORT} told its district groups.",
            "#sansadchalo posts appeared across district groups within hours of the announcement.",
        ),
        (
            "All are invited to join the march, the announcement said, asking district units to arrange buses.",
            "Volunteers were asked to assemble at {venue} by 9 am.",
            "सभी कार्यकर्ता 20 जुलाई को {hi_venue} पहुंचें।",
            "जुलूस निकालेंगे और मांग पत्र सौंपा जाएगा।",
            "The outfit said it had applied for permission and would march regardless of the reply.",
        ),
    ),
    Angle(
        "dharna",
        ("regional", "hindi", "party", "social_hindi"),
        (
            f"{SHORT} volunteers began a dharna outside the {{city}} collectorate on the recruitment calendar.",
            f"{{hi_city}} में {SHORT} कार्यकर्ताओं ने धरना देंगे की घोषणा के बाद कलेक्ट्रेट के बाहर प्रदर्शन शुरू किया।",
            "A relay dharna at {venue} entered its fourth day.",
        ),
        (
            "{count_small} people sat through the afternoon in rotation.",
            "{official} said the gathering had not obtained written permission.",
            "धरना स्थल पर हर दिन नए ज़िलों से कार्यकर्ता पहुंच रहे हैं।",
            "The district unit said the dharna would continue until the calendar is published.",
        ),
    ),
    Angle(
        "mahapanchayat",
        ("hindi", "social_hindi", "regional", "party"),
        (
            f"{{hi_city}} में महापंचायत में {SHORT} ने भर्ती कैलेंडर की मांग दोहराई।",
            "A mahapanchayat at {venue} drew {count_large} by the organisers' count and far fewer by the district administration's.",
            "सभी जिलों के कार्यकर्ता रविवार को आएं, संगठन ने कहा।",
        ),
        (
            "{hi_count} लोग शामिल हुए, आयोजकों का दावा है।",
            "The administration put the crowd at a fraction of the organisers' figure.",
            "महापंचायत में चक्का जाम की चेतावनी भी दी गई।",
            "Speakers repeated that the march would be peaceful.",
        ),
    ),
    Angle(
        "permission-refused",
        ("wire", "national", "opposing", "hindi"),
        (
            f"Police in {{city}} refused permission for the {SHORT} march, citing traffic and examination schedules.",
            f"{{hi_city}} पुलिस ने {SHORT} मार्च की अनुमति देने से इनकार कर दिया।",
        ),
        (
            "{official} said prohibitory orders would be in force on the day.",
            "The outfit said it would proceed and would court arrest if stopped.",
            "संगठन ने कहा कि वह मार्च करेगा।",
            "Two other student bodies said they would join in solidarity.",
        ),
    ),
    Angle(
        "buses-logistics",
        ("social_party", "social_hindi", "party", "partisan"),
        (
            "District units have been asked to confirm bus numbers by Thursday for the march to Parliament Street.",
            "हर ज़िले से बसें रवाना होंगी, कार्यकर्ता सुबह 6 बजे तक पहुंचें।",
            "Volunteers should reach at 7 am at the assembly point, the coordination group said.",
        ),
        (
            "Water and medical volunteers were listed by district.",
            "No banners other than the charter were to be carried, the message said.",
            "पानी और मेडिकल वॉलंटियर की सूची ज़िलेवार जारी की गई है।",
        ),
    ),
)


# ── Phase 4: the march and the police action ───────────────────────────

P4 = (
    Angle(
        "march-day",
        ("wire", "national", "hindi", "regional"),
        (
            f"Thousands of {SHORT} supporters marched towards Parliament Street on Sunday before being stopped at barricades.",
            "संसद चलो मार्च में {hi_count} लोग शामिल हुए, पुलिस ने बैरिकेड पर रोका।",
            f"The {SHORT} march reached the second barricade line before water cannon was used.",
        ),
        (
            "Organisers put the turnout at {count_large}; the police did not give a figure.",
            "Metro stations near the route were closed for four hours.",
            "मेट्रो स्टेशन चार घंटे बंद रहे।",
            "{official} said the crowd had been asked repeatedly to disperse.",
        ),
    ),
    Angle(
        "lathi-charge",
        ("wire", "national", "party", "partisan", "social_party", "hindi"),
        (
            "Police used batons on the crowd at the barricade line, and at least 30 people were injured.",
            "पुलिस ने लाठीचार्ज किया, कई कार्यकर्ता घायल हुए।",
            "Video from the barricade shows batons being used on people who were already sitting down.",
        ),
        (
            "This is what a government does when it has no answer: it beats students in the street.",
            "Hospital records show 14 admissions, three of them with head injuries.",
            "The police said stones were thrown first; the footage from two angles does not show that.",
            "यह शर्मनाक है, बैठे हुए छात्रों पर लाठी चलाई गई।",
            "{official} said an inquiry would be conducted into the use of force.",
        ),
    ),
    Angle(
        "detentions",
        ("wire", "national", "hindi", "party"),
        (
            f"{{count_small}} {SHORT} volunteers were detained and released the same evening.",
            "{hi_count} कार्यकर्ताओं को हिरासत में लिया गया और शाम को छोड़ दिया गया।",
        ),
        (
            "No first information report names any organiser so far.",
            "The outfit said its convener was held for six hours without a reason being recorded.",
            "किसी संगठनकर्ता के खिलाफ प्राथमिकी दर्ज नहीं की गई है।",
        ),
    ),
    Angle(
        "government-reaction",
        ("opposing", "national", "wire"),
        (
            "The government said the march had no permission and that force was used only after barricades were broken.",
            "A minister described the outfit as a front and said the agitation was politically funded.",
        ),
        (
            "No evidence for the funding claim was offered at the briefing.",
            "The opposition demanded a statement in Parliament.",
            "The outfit rejected the characterisation and repeated its four demands.",
        ),
    ),
    Angle(
        "counter-satire",
        ("counter", "social_civic"),
        (
            "Barricades at the third line, water cannon at the second, and a press release calling it a dialogue.",
            "Everyone is now an expert on crowd estimates, including the people who were not there.",
        ),
        (
            "Two hours of footage, four completely different crowd figures, one afternoon.",
            "The figure a channel picks tells you which channel it is, not how many people came.",
        ),
    ),
)


# ── Phase 5: the resignation ───────────────────────────────────────────

P5 = (
    Angle(
        "minister-resigns",
        ("wire", "national", "hindi", "regional", "party", "opposing"),
        (
            "The Education Minister resigned on Friday, five days after the police action on the march.",
            "शिक्षा मंत्री ने शुक्रवार को इस्तीफ़ा दे दिया।",
            "The resignation letter cites personal reasons and does not mention the agitation.",
        ),
        (
            "The outfit called the resignation a vindication of its charter.",
            "Officials said the decision had been under discussion before the march.",
            "इस्तीफ़े में आंदोलन का कोई ज़िक्र नहीं है।",
            "A successor is expected to be named within the week.",
            "Whether the two events are connected is precisely what nobody will state on record.",
        ),
    ),
    Angle(
        "inquiry-ordered",
        ("wire", "national", "hindi"),
        (
            "A judicial inquiry was ordered into the use of force at the barricade line.",
            "लाठीचार्ज की न्यायिक जांच के आदेश दिए गए हैं।",
        ),
        (
            "The inquiry is to report within three months.",
            "Two petitions on the same incident are already before the High Court.",
            "जांच रिपोर्ट तीन महीने में देनी होगी।",
        ),
    ),
    Angle(
        "recruitment-calendar",
        ("national", "regional", "party", "factcheck"),
        (
            "The department published a recruitment calendar for two examinations, one of the outfit's four demands.",
            f"The calendar covers two of the eleven examinations the {SHORT} charter lists.",
        ),
        (
            "The outfit said it would treat the publication as partial compliance.",
            "Aspirants pointed out that the dates are indicative rather than notified.",
            "The department did not respond to a question about the remaining examinations.",
        ),
    ),
)


# ── Phase 6: consolidation, counter-narrative, impersonation ───────────

P6 = (
    Angle(
        "fake-circular",
        ("factcheck", "national", "party", "hindi"),
        (
            f"A circular attributed to the {SHORT} announcing a fee boycott is a forgery, the outfit said.",
            f"{SHORT} के नाम से वायरल परिपत्र फ़र्ज़ी निकला।",
            f"Two sites carrying the {SHORT} name and logo are not run by the outfit.",
        ),
        (
            "The letterhead uses a logo version the outfit stopped using in June.",
            "The domain was registered three weeks ago behind a privacy service.",
            "यह परिपत्र संगठन ने जारी नहीं किया है।",
            "The outfit has asked the platform to act on six impersonating accounts.",
        ),
    ),
    Angle(
        "impersonation-amplified",
        ("partisan", "social_civic", "counter"),
        (
            f"The forged {SHORT} circular was posted by eleven accounts before the outfit denied it.",
            f"A screenshot of a {SHORT} statement nobody can find the original of is doing the rounds again.",
        ),
        (
            "None of the accounts that posted it have deleted the post.",
            "Two of them describe themselves as district units and are not listed by the outfit.",
            "A denial travels at a fraction of the speed of the thing it denies.",
        ),
    ),
    Angle(
        "organisation-building",
        ("party", "national", "regional", "social_party"),
        (
            f"The {SHORT} announced a district committee structure and a membership audit.",
            f"{SHORT} said it would publish audited accounts for its first six months.",
        ),
        (
            "Each district committee is to have five members, two of them women.",
            "The audit is to be conducted by a chartered accountant the outfit will name.",
            "Membership claims will be restated after the audit, {spokesperson} said.",
        ),
    ),
    Angle(
        "counter-campaign",
        ("opposing", "partisan", "counter"),
        (
            f"A campaign questioning the {SHORT}'s funding gathered pace across partisan sites this week.",
            f"The {SHORT} is being investigated by everyone except an investigating agency.",
        ),
        (
            "The claims repeat a single unsourced allegation about foreign funding.",
            "No document supporting the allegation has been produced.",
            "The outfit has said it will publish its accounts, which would settle it either way.",
        ),
    ),
)


# ── Phase 7: the split ─────────────────────────────────────────────────

P7 = (
    Angle(
        "split",
        ("wire", "national", "hindi", "regional", "party"),
        (
            f"The {SUBJECT} split on Wednesday, with a group of conveners announcing the {BREAKAWAY}.",
            f"{SUBJECT} में फूट, कुछ नेताओं ने {BREAKAWAY} बनाने की घोषणा की।",
            f"Four of the eleven founding conveners have left the {SHORT} to form a separate outfit.",
        ),
        (
            "The breakaway group says the parent outfit centralised decisions after the march.",
            "The {SHORT} said the departures involve no district committee.",
            "नई इकाई का कहना है कि निर्णय प्रक्रिया केंद्रीकृत हो गई थी।",
            "Both groups claim the charter.",
        ),
    ),
    Angle(
        "split-reaction",
        ("party", "partisan", "social_party", "opposing", "counter"),
        (
            f"The {SHORT} said the split changes nothing about the recruitment calendar demand.",
            "A movement that could not survive its own success is now two movements that cannot.",
            f"{BREAKAWAY} ने कहा कि उसका एजेंडा वही है।",
        ),
        (
            "Both outfits have announced separate district meetings on the same day.",
            "Aspirants on the ground say they do not know which group to approach.",
            "दोनों संगठनों ने अलग-अलग बैठकें बुलाई हैं।",
            "The demand is unchanged, which is the part nobody is reporting.",
        ),
    ),
    Angle(
        "march-announced-again",
        ("party", "social_party", "social_hindi"),
        (
            "A second Sansad Chalo march has been announced for later this month.",
            "फिर से संसद चलो का ऐलान, सभी कार्यकर्ता तय तारीख़ को पहुंचें।",
        ),
        (
            "Permission has been sought this time, the outfit said.",
            "District units were asked to confirm participation by the weekend.",
            "अनुमति के लिए आवेदन दिया गया है।",
        ),
    ),
)


PHASES: tuple[Phase, ...] = (
    Phase(1, "Founding", date(2026, 5, 15), date(2026, 5, 31), P1, 24),
    Phase(2, "Online growth and the account block", date(2026, 6, 1), date(2026, 6, 30), P2, 28),
    Phase(3, "Street mobilization", date(2026, 7, 1), date(2026, 7, 19), P3, 26),
    Phase(4, "The march and the police action", date(2026, 7, 20), date(2026, 7, 22), P4, 22),
    Phase(5, "The resignation", date(2026, 7, 23), date(2026, 7, 31), P5, 18),
    Phase(6, "Consolidation and counter-narrative", date(2026, 8, 1), date(2026, 8, 31), P6, 22),
    Phase(7, "The split", date(2026, 9, 1), date(2026, 9, 10), P7, 18),
)


# Publication Time signals, in the proportion a real news corpus produces
# them. A share of items carries none at all, because an importer that never
# sees a null never exercises the timeline's exclusion footnote.
SIGNALS: tuple[tuple[str, int], ...] = (
    ("jsonld_date_published", 55),
    ("opengraph_published_time", 20),
    ("url_path_date", 15),
    ("meta_article_published", 10),
)

SOCIAL_SIGNAL = "platform_api_timestamp"
NO_DATE_SHARE = 0.06


def _weighted(rng: random.Random, weights: Iterable[tuple[str, int]]) -> str:
    items = list(weights)
    total = sum(w for _, w in items)
    roll = rng.randint(1, total)
    for value, weight in items:
        roll -= weight
        if roll <= 0:
            return value
    return items[-1][0]


def _fill(rng: random.Random, template: str) -> str:
    """Substitute every slot the template names, drawing each independently."""
    out = template
    for key, pool in SLOTS.items():
        token = "{" + key + "}"
        while token in out:
            out = out.replace(token, rng.choice(pool), 1)
    return out


def _is_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def _pick_outlet(rng: random.Random, angle: Angle, want_hindi: bool) -> Optional[Outlet]:
    """An outlet whose voice the angle allows, and whose language fits the text.

    A Hindi sentence attributed to an English-language wire service is a
    collection artefact, not a corpus, so the language of the drawn text
    decides the outlet rather than the other way round.
    """
    pool = [o for v in angle.voices for o in BY_VOICE.get(v, ())]
    if want_hindi:
        pool = [o for o in pool if o.language == "hi"] or [o for o in OUTLETS if o.language == "hi"]
    else:
        pool = [o for o in pool if o.language == "en"]
    return rng.choice(pool) if pool else None


def _slug(text: str, limit: int = 7) -> str:
    words = [w.strip(".,:;'\"").lower() for w in text.split() if w.isascii() and w.isalpha()]
    return "-".join(words[:limit]) or "item"


def _timestamp(rng: random.Random, phase: Phase) -> datetime:
    span = (phase.end - phase.start).days
    day = phase.start + timedelta(days=rng.randint(0, max(span, 0)))
    return datetime(
        day.year,
        day.month,
        day.day,
        rng.randint(7, 22),
        rng.choice((0, 5, 12, 17, 23, 38, 41, 55)),
        tzinfo=IST,
    )


def _build_item(
    rng: random.Random, phase: Phase, angle: Angle, seq: int
) -> Optional[dict[str, Any]]:
    lead = _fill(rng, rng.choice(angle.lead))
    hindi = _is_devanagari(lead)
    outlet = _pick_outlet(rng, angle, hindi)
    if outlet is None:
        return None

    body_pool = [b for b in angle.body if _is_devanagari(b) == hindi]
    if not body_pool:
        body_pool = list(angle.body)
    sentences = [lead]
    for template in rng.sample(body_pool, min(len(body_pool), rng.randint(2, 3))):
        sentences.append(_fill(rng, template))
    text = " ".join(sentences)

    published = _timestamp(rng, phase)
    dated = rng.random() > NO_DATE_SHARE
    social = outlet.platform != "web"

    if social:
        url = f"https://{outlet.host}/{outlet.handle.lstrip('@')}/{published:%Y%m%d}{seq:03d}"
        discovery = "adapter_paging"
        body_source = "publisher"
        signal = SOCIAL_SIGNAL
    else:
        url = f"https://{outlet.host}/{published:%Y/%m/%d}/{_slug(lead)}-{seq:03d}"
        discovery = rng.choice(("archive_sitemap", "paginated_feed", "topic_feed"))
        body_source = "publisher" if rng.random() > 0.15 else "archive"
        signal = _weighted(rng, SIGNALS)

    item: dict[str, Any] = {
        "url": url,
        "text": text,
        "language": "hi" if hindi else "en",
        "discovery": discovery,
        "body_source": body_source,
        "source": {
            "handle": outlet.handle,
            "name": outlet.name,
            "platform": outlet.platform,
        },
    }
    if dated:
        item["published_at"] = published.isoformat()
        item["published_at_signal"] = signal
    return item


HEADER = f"""# SYNTHETIC CORPUS. Every item below is invented, including the outlets,
# the handles, the dates and the text. Generated by
# scripts/gen_synthetic_corpus.py, which is deterministic for a given seed.
#
# This file is NOT the demonstration corpus and must never be presented as
# collected material. The demonstration corpus is built by
# scripts/build_corpus.py against infra/configs/corpora/, and its claim to an
# evaluating officer is that it fabricates no timestamp and no outlet. This
# file fabricates all of them, on purpose, so that the workbench and the
# detection path can be developed against a populated database.
#
# Subject: {SUBJECT}, a fictional treatment of the arc in
# docs/demonstration_dataset_plan.md. Every host is under a reserved example
# domain, so no real outlet is impersonated.
"""


def generate(seed: int) -> list[str]:
    rng = random.Random(seed)
    lines: list[str] = [HEADER.rstrip("\n")]
    seen: set[str] = set()
    seq = 0

    for phase in PHASES:
        lines.append("#")
        lines.append(f"# Phase {phase.number}: {phase.name}, {phase.start} to {phase.end}")
        produced = 0
        attempts = 0
        while produced < phase.items and attempts < phase.items * 40:
            attempts += 1
            angle = rng.choice(phase.angles)
            seq += 1
            item = _build_item(rng, phase, angle, seq)
            if item is None or item["text"] in seen:
                continue
            seen.add(item["text"])
            lines.append(json.dumps(item, ensure_ascii=False))
            produced += 1
        if produced < phase.items:
            print(
                f"phase {phase.number}: produced {produced} of {phase.items} "
                "distinct items; widen the angle pools",
                file=sys.stderr,
            )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic corpus")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("corpora/synthetic_cockroach_janta_party.jsonl"),
        help="Output path. The name must start with synthetic_.",
    )
    parser.add_argument(
        "--seed", type=int, default=54, help="RNG seed; output is deterministic for it"
    )
    args = parser.parse_args()

    if not args.out.name.startswith("synthetic_"):
        print(
            "Refusing to write a generated corpus under a name that does not "
            "start with synthetic_. A fabricated corpus that reads as a "
            "collected one is the failure this check exists to prevent.",
            file=sys.stderr,
        )
        return 1

    lines = generate(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    items = sum(1 for line in lines if line.startswith("{"))
    print(f"  [+] {items} items written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
