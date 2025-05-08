import json

# Schema definition for name list records with full required fields
MILITARY_RECORD_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Запись именного списка",
    "type": "object",
    "properties": {
      "Issue": {
        "type": "integer",
        "description": "Номер списка или документа. Символ \" означает то же значение, что и в ячейке выше."
      },
      "Page": {
        "type": "integer", 
        "description": "Номер страницы, где запись документирована. Символ \" означает то же значение, что и в ячейке выше."
      },
      "Province": {
        "type": "string",
        "description": "Губерния или провинция. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s-]+$"
      },
      "Rank": {
        "type": "string",
        "description": "Должность, звание или статус лица на момент записи. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "Surname": {
        "type": "string",
        "description": "Фамилия лица. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s-]+$"
      },
      "Forename": {
        "type": "string",
        "description": "Имя лица. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s-]+$"
      },
      "Middle_name": {
        "type": "string",
        "description": "Отчество лица, если применимо. Символ \" означает то же значение, что и в ячейке выше. Может быть null.",
        "nullable": True,
        "pattern": "^[А-Яа-яЁё\\s-]*$"
      },
      "Religion": {
        "type": "string",
        "description": "Религиозная принадлежность лица. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "Marital_status": {
        "type": "string",
        "description": "Семейное положение лица на момент записи. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "County": {
        "type": "string",
        "description": "Уезд или район. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s-]+$"
      },
      "Town": {
        "type": "string",
        "description": "Населенный пункт происхождения лица. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "Place": {
        "type": "string",
        "description": "Дополнительная информация о месте, если применимо. Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "Casualty_type": {
        "type": "string",
        "description": "Тип статуса или события (например, назначен, уволен, находится). Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^[А-Яа-яЁё\\s.-]+$"
      },
      "Date_DD": {
        "type": "integer",
        "description": "День события или назначения. Символ \" означает то же значение, что и в ячейке выше.",
        "minimum": 1,
        "maximum": 31,
        "nullable": True
      },
      "Date_MMM": {
        "type": "string",
        "description": "Месяц события в сокращенной форме (например, 'Янв', 'Фев'). Символ \" означает то же значение, что и в ячейке выше.",
        "pattern": "^(Янв|Фев|Мар|Апр|Май|Июн|Июл|Авг|Сен|Окт|Ноя|Дек)$",
        "nullable": True
      },
      "Date_YYYY": {
        "type": "integer",
        "description": "Год события или назначения. Символ \" означает то же значение, что и в ячейке выше.",
        "minimum": 1800,
        "maximum": 1950,
        "nullable": True
      }
    },
    "required": [
      "Issue",
      "Page",
      "Province",
      "Rank",
      "Surname",
      "Forename",
      "Religion",
      "Marital_status",
      "County",
      "Town",
      "Place",
      "Casualty_type",
      "Date_DD",
      "Date_MMM",
      "Date_YYYY"
    ],
    "additionalProperties": False
}

# Example records showing both Place field and various Casualty types
EXAMPLE_RECORDS = """
Документ 2682, страница 70. Бессарабская губ. Рядовой Иванов Петр Николаевич, православный, женат. Московский уезд, деревня Пушкино. Ранен 15 Мар 1915.

Документ 2682, страница 70. ", Капитан Попов Петр Николаевич, православный, женат. Могилев уезд, с. Тирасполь, Находится, Кафа. 16 Авг 1897.

Документ 2682, страница 70. ", Поручик Сидоров Иван Иванович, православный, холост. Аккерман. уезд, г. Аккерман., Вставлена, Анапа. Убит 20 Авг 1915.

Документ 2682, страница 70. ", Подпоручик Петров Николай, православный, женат. Кишинев. уезд, с. Кишиневь. Пропал без вести 22 Июн 1917.

Документ 2682, страница 70. ", Ефрейтор Миронов, православный, холост. Измаил уезд, с. Измаил, Уйлия Диорм. Убит 3 Май 1916.

Документ 2682, страница 70. ", Унтер-офицер Васильев Алексей Иванович, православный, женат. Тверской уезд, город Ржев, Центр. площадь. Находится 10 Янв 1918.
"""

# Expected JSON output showing proper Place and Casualty_type extraction
EXAMPLE_JSON_OUTPUT = """
[
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Рядовой",
    "Surname": "Иванов",
    "Forename": "Петр",
    "Middle_name": "Николаевич",
    "Religion": "православный",
    "Marital_status": "женат",
    "County": "Московский",
    "Town": "Пушкино",
    "Place": null,
    "Casualty_type": "Ранен",
    "Date_DD": 15,
    "Date_MMM": "Мар",
    "Date_YYYY": 1915
  },
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Капитан",
    "Surname": "Попов",
    "Forename": "Петр",
    "Middle_name": "Николаевич",
    "Religion": "православный",
    "Marital_status": "женат",
    "County": "Могилев",
    "Town": "Тирасполь",
    "Place": "Находится, Кафа",
    "Casualty_type": null,
    "Date_DD": 16,
    "Date_MMM": "Авг",
    "Date_YYYY": 1897
  },
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Поручик",
    "Surname": "Сидоров",
    "Forename": "Иван",
    "Middle_name": "Иванович",
    "Religion": "православный",
    "Marital_status": "холост",
    "County": "Аккерман.",
    "Town": "Аккерман.",
    "Place": "Вставлена, Анапа",
    "Casualty_type": "Убит",
    "Date_DD": 20,
    "Date_MMM": "Авг",
    "Date_YYYY": 1915
  },
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Подпоручик",
    "Surname": "Петров",
    "Forename": "Николай",
    "Middle_name": null,
    "Religion": "православный",
    "Marital_status": "женат",
    "County": "Кишинев.",
    "Town": "Кишиневь",
    "Place": null,
    "Casualty_type": "Пропал без вести",
    "Date_DD": 22,
    "Date_MMM": "Июн",
    "Date_YYYY": 1917
  },
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Ефрейтор",
    "Surname": "Миронов",
    "Forename": null,
    "Middle_name": null,
    "Religion": "православный",
    "Marital_status": "холост",
    "County": "Измаил",
    "Town": "Измаил",
    "Place": "Уйлия Диорм",
    "Casualty_type": "Убит",
    "Date_DD": 3,
    "Date_MMM": "Май",
    "Date_YYYY": 1916
  },
  {
    "Issue": 2682,
    "Page": 70,
    "Province": "Бессарабская",
    "Rank": "Унтер-офицер",
    "Surname": "Васильев",
    "Forename": "Алексей",
    "Middle_name": "Иванович",
    "Religion": "православный",
    "Marital_status": "женат",
    "County": "Тверской",
    "Town": "Ржев",
    "Place": "Центр. площадь",
    "Casualty_type": "Находится",
    "Date_DD": 10,
    "Date_MMM": "Янв",
    "Date_YYYY": 1918
  }
]
"""