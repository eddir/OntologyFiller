# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString

from natasha import NamesExtractor, MorphVocab, Segmenter, Doc, NewsEmbedding, NewsMorphTagger, NewsSyntaxParser
from natasha.grammars.addr import DOT, INT
from yargy import Parser, rule, not_, or_, predicates
from yargy.interpretation.normalizer import Normalizer
from yargy.predicates import (
    eq, type, caseless, in_, in_caseless,
    gte, lte, length_eq,
    is_capitalized, normalized,
    dictionary, gram,
)
from yargy.interpretation import fact
from yargy.pipelines import morph_pipeline
from yargy.predicates import eq
from yargy.relations import gnc_relation
from yargy.tokenizer import (
    QUOTES,
    LEFT_QUOTES,
    RIGHT_QUOTES,

    MorphTokenizer,
    TokenRule, OTHER, EOL
)

from ontology import OntoFacts, OntoGroup, OntoFact


def join_spans(text, spans):
    spans = sorted(spans)
    return ' '.join(
        text[start:stop]
        for start, stop in spans
    )


def get_facts(text):
    QUOTE = in_(QUOTES)
    HYPHEN = dictionary(['-', '—', '–'])
    facts = OntoFacts()

    parser = NamesExtractor(MorphVocab())
    matches = parser(text)
    match = [_.fact for _ in matches][0]
    if match.first is not None:
        # remove None
        fio = [x for x in [match.last, match.first, match.middle] if x is not None]
        facts.add_fact('Scientist', ' '.join(fio))

    Department = fact(
        'Department',
        ['definition', 'name', 'position']
    )

    POSITION = rule(
        morph_pipeline([
            'доцент',
            'аспирант',
            'ассистент',
            'профессор'
        ])
    )

    NAME = rule(
        QUOTE,
        not_(QUOTE).repeatable(),
        QUOTE
    )
    DEFINITION = rule(
        morph_pipeline(['кафедра', 'отдел']),
        NAME
    ).interpretation(Department.definition)
    POSITION_SET = rule(HYPHEN, POSITION.interpretation(Department.position))

    department = rule(DEFINITION, POSITION_SET).interpretation(Department)

    parser = Parser(department)
    for match in parser.findall(text):
        facts.add_fact('Department', match.fact.definition)

    DISERTATION_TYPE = rule(
        morph_pipeline([
            "кандидатская",
            "докторская",
            "магистерская"
        ])
    )

    Thesis = fact(
        'Thesis',
        ['kind', 'title', 'speciality', 'degree', 'branch']
    )

    TITLE = rule(
        not_(QUOTE).repeatable().optional(),
        QUOTE,
        not_(QUOTE).repeatable().interpretation(Thesis.title),
        QUOTE
    )

    THESIS_NAME = rule(
        DISERTATION_TYPE.optional().interpretation(Thesis.kind),
        morph_pipeline(['диссертация']),
        TITLE
    ).interpretation(Thesis)

    DEGREE_TYPE = rule(
        or_(normalized('кандидат'), normalized('доктор'))
    )

    Speciality = fact(
        'Speciality',
        ['code', 'hyphen', 'name']
    )

    SPECIALITY_CODE = rule(
        rule(
            INT.repeatable(),
            eq('.'),
            INT.repeatable(),
            eq('.'),
            INT.repeatable()
        ).interpretation(Speciality.code),
        HYPHEN.interpretation(Speciality.hyphen)
    )

    SPECIALITY_TITLE = rule(
        SPECIALITY_CODE,
        or_(rule(
            QUOTE,
            not_(QUOTE).repeatable().interpretation(Speciality.name),
            QUOTE
        ), rule(
            not_(or_(
                eq('.'),
                eq(';'))
            ).repeatable().interpretation(Speciality.name)
        ))
    ).interpretation(Speciality)

    SCIENCE_DIRECTION = rule(
        morph_pipeline([
            'направление',
            'специальность'
        ])
    )

    Branch = fact(
        'Branch',
        ['name']
    )

    BRANCH = rule(
        not_(eq('наук')).repeatable().interpretation(Branch.name.normalized()),
    ).interpretation(Branch)

    AcademicDegree = fact(
        'AcademicDegree',
        ['degree', 'branch', 'suffix']
    )

    ACADEMIC_DEGREE = rule(
        DEGREE_TYPE.interpretation(AcademicDegree.degree.normalized()),
        BRANCH.interpretation(AcademicDegree.branch),
        eq('наук').interpretation(AcademicDegree.suffix)
    ).interpretation(AcademicDegree)

    SPECIALITY_DEGREE = rule(
        not_(or_(eq('кандидата'), eq('доктора'))).repeatable(),
        ACADEMIC_DEGREE.interpretation(Thesis.degree)
    )

    SPECIALITY = rule(
        SPECIALITY_DEGREE.optional(),
        eq('по'),
        SCIENCE_DIRECTION,
        SPECIALITY_TITLE.interpretation(Thesis.speciality)
    )

    thesis = rule(THESIS_NAME, SPECIALITY).interpretation(Thesis)

    parser = Parser(thesis)
    for match in parser.findall(text):
        info = [
            ['Thesis ', match.fact.title],
        ]
        if match.fact.speciality:
            if match.fact.speciality.code:
                if match.fact.speciality.hyphen:
                    info.append(['Speciality', " ".join([
                        match.fact.speciality.code,
                        match.fact.speciality.hyphen,
                        match.fact.speciality.name
                    ])])
                else:
                    info.append(['Speciality', " ".join([
                        match.fact.speciality.code,
                        match.fact.speciality.name
                    ])])
            else:
                info.append(['Speciality', match.fact.speciality.name])

        if match.fact.degree:
            info.append(['AcademicDegree', match.fact.degree.degree])
            info.append(['BranchOfScience', match.fact.degree.branch.name])

        facts.add_facts(info)

    emb = NewsEmbedding()
    morph_tagger = NewsMorphTagger(emb)
    syntax_parser = NewsSyntaxParser(emb)
    segmenter = Segmenter()
    doc = Doc(text)

    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    doc.parse_syntax(syntax_parser)

    sent = doc.sents[1]
    sent.morph.print()


    return facts


def get_xml(items, url):
    xml = ET.Element('fdo_objects')
    document = ET.SubElement(xml, 'document')
    document.set('url', url)
    document.set('date', '')
    facts_element = ET.SubElement(document, 'facts')
    for item in items:
        fact_element = ET.SubElement(facts_element, 'Fact')
        fact_element.set('FactID', str(item.id))
        fact_element.set('LeadID', str(item.id))
        for f in item.facts:
            if f.value:
                field = ET.SubElement(fact_element, f.type)
                field.set('val', f.value)

    return ET.tostring(xml, encoding='utf-8', method='xml').decode('utf-8')


def pretty_print(xml):
    if xml:
        print(parseString(xml).toprettyxml())
    else:
        print('No facts found')


def main():
    resume = """
        Шульга Татьяна Эриковна
    доктор физико-математических наук , профессор

        Институт прикладных информационных технологий и коммуникаций — кафедра "Информационно-коммуникационные системы и программная инженерия" — Профессор

    Научная тематика

        Онтологический инжиниринг знаний
        Разработки математических моделей и методов организации управления дискретными системами, математическим аппаратом исследования является теория автоматов, алгебра и теория чисел

    Образование и карьера

    1997 – окончила механико-математический факультет Саратовского государственного университета имени Н.Г. Чернышевского по специальности «Прикладная математика» с присуждением квалификации «Математик».

2000 – защитила кандидатскую диссертацию «Методы и модели функционального восстановления поведения систем, моделируемых автоматами специального класса» на соискание            степени кандидата физико-математических наук по специальности «Математическая кибернетика».
            защитила диссертацию «Математическое моделирование динамических процессов в дискретно-континуальных системах»                                   на соискание ученой степени кандидата физико-математических наук по специальности 05.13.18 – «Математическое моделирование, численные методы и комплексы программ».
    1998-2005 - работала в преподавательских должностях (ассистента, доцента) на механико-математическом факультете и факультете компьютерных наук и информационных технологий Саратовского государственного университета имени Н.Г. Чернышевского.

    2003 – получила ученное звание доцента по кафедры «Теоретических основ информатики и информационных технологий»

    2003-2011 – возглавляла факультет информатики и информационных технологий Саратовского государственного социально-экономического университета, была профессором кафедры прикладной математики и информатики СГСЭУ.

    2010 – защитила диссертацию «Математические модели функционально избыточных дискретных систем» doc на соискание ученой степени доктора физико-математических наук по специальности 05.13.18 – «Математическое моделирование, численные методы и комплексы программ».

    2012-2016 – возглавляла кафедру «Прикладная информатика и программная инженерия» Саратовского государственного технического университета имени Гагарина Ю.А.

    2017 - получила ученое звание профессора по специальности «Математическое моделирование, численные методы и комплексы программ»

    2016 – по настоящее время работает профессором кафедры «Информационно-коммуникационные системы и программная инженерия».

    Является автором более 15 лекционных курсов, 16 учебных изданий. Является членом УМО УГСН «Информатика и вычислительная техника» (УМС «Прикладная информатика», г. Москва). Активно внедряет новые формы обучения и информационные технологии в образовательный процесс. Под руководством Шульги Т.Э. защищено более 40 выпускных квалификационных работ, магистерских диссертаций. Ежегодно, студенты СГТУ под ее руководством участвуют в конкурсах и конференциях различного уровня, публикуют печатные работы и занимают призовые места, в частности в 2015 году магистерская диссертация Данилова Н.А., получила диплом 1 степени на всероссийском конкурсе магистерских диссертаций по направлению «Прикладная информатика». В 2016 году четверо студентов под руководством Шульги Т.Э. награждены стипендиями президента и правительства РФ. За время работы в СГТУ имени Гагарина Ю.А. Шульгой Т.Э., совместно со студентами и аспирантами получено 10 свидетельств о регистрации программы для ЭВМ.

    Шульга Т.Э. постоянно повышает свою профессиональную квалификацию, только за последние 4 года получила 5 международных сертификатов. Учувствует в проекте Tempus PICTET: EQF-based professional ICT training for Russia and Kazakhstan

    Шульга Т.Э. активно работает как ученый. Имеет более 120 научных работ, в т.ч. две монографии, ежегодно участвует с докладами в всероссийских и международных конференциях. Является членом двух диссертационных советов Д 212.242.04, Д 212.242.08, руководит работой аспирантов (трое из которых были удостоены стипендий президента и правительства РФ), готовит кандидатов и докторов наук. Ежегодно с 2013 года входит в организационный комитет международных конференций «Проблемы управления в социально-экономических и технических системах», «Проблемы управления, обработки и передачи информации», Математические методы в технике и технологиях». Являлась ответственным исполнителем гранта Министерства образования РФ «Разработка требований к региональным порталам и порталам учебных заведений и создание типовых блоков программного обеспечения для их реализации» (2003), ответственным исполнителем гранта Министерства образования РФ по проекту «Разработка и внедрение модели организации учебного процесса в системе ОО Саратовского региона на примере интегрированного университета» (2001-2002). исполнителем гранта РФФИ № 98-01-00835 (1998-2001) и многочисленных проектов в рамках федеральных целевых программ по информатизации (2002-2011 гг). В 2011-2016 гг являлась исполнителем государственного задания вузам на выполнение НИР по мероприятию «Проведение фундаментальных и прикладных научных исследований и экспериментальных разработок» (программа «Разработка методов дискретного анализа семантики слабоструктурированных систем»). В настоящий момент является исполнителем НИР в рамках проектной части государственного задания Минобрнауки РФ в сфере научной деятельности – задание № 9.2108.2017/ПЧ «Разработка и экспериментальная отработка теоретических основ применения комплексов с беспилотными летательными аппаратами вертолетного типа взлетной массой до 500 кг при выполнении поисково-спасательных операций на воде».

    Повышение квалификации

        2004 – Москва, Учебный цент SoftLine - Мастер-класc для инструкторов Microsoft IT Academy
        2005 – Саратов, ООО «Яндекс» - диплом практического семинара «Поисковая интернет-реклама. Рекламные возможности Яндекса»
        2008 – Саратов, СГСЭУ - сертификат о повышении квалификации (72 часа) «Основные требования ГОСТ Р ИСО 9001:2001, методология процессного подхода и возможности его применения для совершенствования СМК вуза»
        2011 – Германия, Берлин, Beuth Hochshule für Technik (University of Applied Sciences) - курс «Data Mining and Data Warehouse Data» (Интеллектуальный анализ данных и хранилища данных)
        2011 – Германия, Берлин, Beuth Hochshule für Technik (University of Applied Sciences) - курс «Software Architecture» (Архитектура программного обеспечения)
        2012 – Саратов, международный образовательный центр Aptech - Aptech Certified Trainer in the skill «Logic Building in C» (сертифицированный преподаватель Aptech по курсу«Программирование на языке С»)
        2011-2013 – Саратов, СГТУ имени Гагарина Ю.А. - удостоверения государственного образца о краткосрочном повышении квалификации (74 часа) по профилю специальности 031202.65 «Перевод и переводоведение» по дополнительной образовательной программе «Практический курс английского языка»
        2013 – Москва, учебный центр Hewlett-Packard - курс «ITIL® V3 Foundation: Основы ITIL для управления ИТ-услугами» с получением международного сертификата ITIL Foundation Certificate in IT Service Management (EXIN, Нидерланды)
        2014 – София, Болгария, Государственный университет библиотечных наук и информационных технологий, курс «Competencebased framework for curriculum development» (72 часа) (в рамках проекта Tempus PICTET: EQF-based professional ICT training for Russia and Kazakhstan)
        2015 - Салоники, Греция, Александрийский технологический институт Салоники, курс «New teaching methods for professional ICT training» 72 часа ) (в рамках проекта Tempus PICTET: EQF-based professional ICT training for Russia and Kazakhstan)
        2015 - Саратов, Международный образовательный центр Aptech - Aptech Certified Trainer in the skill “C#” (Сертифицированный преподаватель Aptech по курсу «Язык С#»)
        2015 - Саратов, СГТУ имени Гагарина Ю.А., удостоверение о повышении квалификации по дополнительной профессиональной программе повышения квалификации «Информационно-образовательная среда вуза как условие применения современных образовательных технологий» по профилю направления 230400.62 «Информационные системы и технологии».  
        2015 - Саратов, СГТУ имени Гагарина Ю.А. – Программа профессиональной переподготовки «Разработка и программирование информационных систем на основе современных компьютерных моделей и методов с использованием баз данных и интеллектуальных технологий» по профилю направлению 09.04.02 «Информационные системы и технологии» (диплом о профессиональной переподготовке)
        2018 - Саратов, СГТУ имена Гагарина Ю.А. – Программа профессиональной переподготовки «Преподаватель высшего образования» по профилю направления 37.03.01 «Психология», профиль дисциплин «Программная инженерия», «Программирование» (диплом о профессиональной переподготовке).

    Основные публикации

        A.A. Sytnik, T.E. Shulga Functional Renewal of Behavior of Systems: Numerical Methods// Automation and Remote Control. 2003. Vol. 64. No. 10. pp. 1620-1634. Translated from Automatika i Telemehanika. 2003. No. 10. pp. 123-139.
         Сытник А.А., Шульга Т.Э. О восстановлении систем, моделируемых автоматами // Интеллектуальные системы. Научный журнал. - М.: Изд-во МГУ, 2005. - Т. 9. - Вып. 1-4. - С. 265-279.
         Сытник А.А., Шульга Т.Э., Папшев С.В. Управление поведением мехатронных систем на основе свойств функциональной избыточности // Мехатроника, автоматизация, управление. - М.: Изд-во «Новые технологии», 2008. - № 12. - С. 41-44.
         Шульга Т.Э. О классе систем, разрешимом относительно задачи управления поведением на основе свойств функциональной избыточности //Вестник СГТУ. - 2008. - № 4. - С. 57-64. monitor.png
         Шульга Т.Э. Метод построения восстанавливающих последовательностей для систем без потери информации // Системы управления и информационные технологии. - Воронеж: Изд-во Ворон. гос. тех. ун-та, 2009. - № 1.3 (35). - С. 407-411.
        Шульга Т.Э. Организационные принципы подготовки IT-специалистов//Прикладная информатика №3(21) 2009. С.49-53.
         Шульга Т.Э. Общая схема управления дискретными системами на основе функциональной избыточности //Современные технологии. Системный анализ. Моделирование. 2010. №1 (25). С. 167-175.
        Сластихина М.Д., Сытник А.А., Шульга Т.Э. О подходе к проектированию функционально избыточных систем, заданных автоматами специального класса //Вестник СГТУ. 2013. №4 (73). С.167-175. 
        Данилов Н.А., Шульга Т.Э. Построение тепловой карты на основе точечных данных об активности пользователя приложения// Прикладная информатика. 2015. Т. 10. № 2 (56). С. 49-58.
        Романов С.В., Сытник А.А., Шульга Т.Э. О возможностях использования коммуникативных грамматик и LSPL-шаблонов для автоматического построения онтологий//Известия Самарского научного центра Российской академии наук. 2015. т. 17, №2(5). C. 1104-1108.
         Математические модели адаптивных дискретных систем: монография / А.А. Сытник, Т.Э. Шульга. Саратов: Сарат. гос. техн. ун-т, 2015. 272 с.
         T. E. Shulga, E. A. Ivanov, M. D. Slastihina, and N. S. Vagarina Developing a Software System for Automata-Based Code Generation// Programming and Computer Software, 2016, Vol. 42, No. 3, pp. 167–173.
         Danilov N., Shulga T., Frolova N., Melnikova N., Vagarina N., Pchelintseva E. Software Usability Evaluation Based on the User Pinpoint Activity Heat Map // Proceedings of the 5th Computer Science On-line Conference 2016 (CSOC2016), Software Engineering Perspectives and Application in Intelligent Systems – Vol. 2, – Springer 2016, – pp. 217-225. 
        Сытник А.А., Шульга Т.Э., Данилов Н.А. Онтология предметной области "Удобство использования программного обеспечения"// Труды института системного программирования РАН. Том. 30. №2. 2018. С.195-214.
    """
    facts = get_facts(resume)
    pretty_print(get_xml(facts, "\\shulga_tatyana_erikovna.xml"))


if __name__ == '__main__':
    main()
