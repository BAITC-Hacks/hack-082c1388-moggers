"""Topic boundary shared by online and offline assistant modes."""
import re

REFUSAL = (
    "Я помогаю только с анализом финансового графа: переводами, связями счетов, "
    "ролями узлов, кластерами и рисками по данным проекта. "
    "Например, спросите: «Кого проверить первым?» или «Кто переводит деньги этому узлу?»"
)

ARITHMETIC = re.compile(r"\d\s*[+*/×÷=−]\s*\d|^\s*\d+\s*-\s*\d+\s*[?=]?\s*$")
TOPIC = re.compile(
    r"\b\d{15,20}\b|\b(?:gid|aml|seed|moneygraph|node|cluster|transaction|transfer|graph)\b|"
    r"перевод|транзакц|ден[еь]г|счет|счёт|уз[еао]л|кластер|координатор|консолидатор|"
    r"распределител|контрагент|плательщик|получател|отправител|транзит|приоритет|"
    r"отмыван|финансов|кого (?:смотреть|проверить)|кто главн|что (?:ты )?умеешь",
    re.IGNORECASE,
)
FOLLOWUP = re.compile(
    r"^(?:а )?(?:почему|подробнее|объясни|продолжи|что дальше|кто ему платит|"
    r"кому он платит|что это значит|что запросить|каких данных не хватает)[?!.\s]*$",
    re.IGNORECASE,
)


def locally_relevant(question: str, has_context: bool = False) -> bool:
    # Arithmetic is outside the assistant's remit even when wrapped in topic keywords.
    if ARITHMETIC.search(question):
        return False
    return bool(TOPIC.search(question) or (has_context and FOLLOWUP.fullmatch(question.strip())))
