"""Real MedlinePlus Connect / health-topic web service responses recorded on 2026-10-08, keyed by the request that
produced them; replayed by the unit tests of the adapter. No network."""

from typing import Any
from urllib.parse import urlencode


def request_key(url: str, params: dict[str, Any] | None) -> str:
    """Stable key for a (url, params) pair, matching how the fixtures were recorded."""
    return url + "?" + urlencode(sorted((params or {}).items()))


RECORDED: dict[str, Any] = {
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=3&rettype=topic&term=chronic+fatigue+syndrome&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>chronic fatigue syndrome</term>\n"
        "  <file>viv_gFhgUg</file>\n"
        "  <server>pvlb7srch16</server>\n"
        "  <count>29</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>3</retmax>\n"
        '  <list num="29" start="0" per="3">\n'
        '    <document rank="0" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Myalgic encephalomyelitis/chronic fatigue syndrome '
        "(ME/CFS) is a long-term illness. It causes severe fatigue and many other symptoms. "
        'Learn about managing them." title="Myalgic Encephalomyelitis/Chronic Fatigue Syndrome" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89" language="English" date-created="02/19/1999">\n'
        "          <also-called>CFS</also-called>\n"
        "          <also-called>Chronic fatigue syndrome</also-called>\n"
        "          <also-called>ME/CFS</also-called>\n"
        "          <also-called>Myalgic encephalomyelitis</also-called>\n"
        "          <also-called>SEID</also-called>\n"
        "          <also-called>Systemic exertion intolerance disease</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is myalgic encephalomyelitis/chronic fatigue "
        "syndrome (ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is a serious, "
        "long-term illness that affects many body systems. Another name for it is chronic "
        "fatigue syndrome (CFS). ME/CFS can often make you unable to do your usual activities. "
        "Sometimes you may not even be able to get out of bed.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes myalgic encephalomyelitis/chronic fatigue syndrome "
        "(ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Researchers don't yet know what causes ME/CFS. There may be more than one "
        "potential cause. It is also possible that two or more triggers might work together to "
        "cause the illness.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;Researchers are studying many possible causes, "
        "including:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/bonesjointsandmuscles.html" '
        'id="10">Bones, Joints and Muscles</group>\n'
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="1821" language="Spanish">Encefalomielitis miálgica/Síndrome de fatiga '
        "crónica</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D015673">Fatigue Syndrome, Chronic</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/fatigue.html" '
        'id="5324">Fatigue</related-topic>\n'
        "          <see-reference>CFS</see-reference>\n"
        "          <see-reference>Chronic Fatigue Syndrome</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" url="https://medlineplus.gov/fatigue.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Are you tired? Find out about some of the common and '
        'uncommon causes of fatigue and how to help yourself. " title="Fatigue" '
        'url="https://medlineplus.gov/fatigue.html" id="5324" language="English" '
        'date-created="03/08/2010">\n'
        "          <also-called>Tiredness</also-called>\n"
        "          <also-called>Weariness</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue is a feeling of weariness, tiredness, or lack of energy. It can "
        "interfere with your usual daily activities. Fatigue can be a normal response to "
        "physical activity, emotional &lt;a "
        'href="https://medlineplus.gov/stress.html"&gt;stress&lt;/a&gt;, boredom, or lack of '
        "sleep. But sometimes it can be a sign of a mental or physical condition. If you have "
        "been feeling tired for weeks, contact your health care provider. They can help you "
        "find out what's causing your fatigue and recommend ways to relieve it.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue itself is not a disease; it's a symptom. It can have many different "
        "causes, including &lt;a "
        'href="https://medlineplus.gov/pregnancy.html"&gt;pregnancy&lt;/a&gt; and various '
        "medical problems, treatments, and lifestyle habits such as:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/symptoms.html" id="31">Symptoms</group>\n'
        '          <language-mapped-topic url="https://medlineplus.gov/spanish/fatigue.html" '
        'id="5325" language="Spanish">Fatiga</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D005221">Fatigue</descriptor>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89">Myalgic Encephalomyelitis/Chronic Fatigue Syndrome</related-topic>\n'
        "          <see-reference>Tiredness</see-reference>\n"
        "          <see-reference>Weariness</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Anyone who had COVID-19 can have ongoing symptoms. '
        "Learn about post-COVID conditions (long COVID), including symptoms, diagnosis, "
        'treatments, and prevention." title="Post-COVID Conditions (Long COVID)" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807" '
        'language="English" date-created="09/20/2022">\n'
        "          <also-called>Chronic COVID</also-called>\n"
        "          <also-called>Long-haul COVID</also-called>\n"
        "          <also-called>Long-term effects of COVID</also-called>\n"
        "          <full-summary>&lt;h3&gt;What are post-COVID conditions (long "
        "COVID)?&lt;/h3&gt;\n"
        "&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt; '
        "(coronavirus disease 2019) is an illness caused by a virus. Many people get better "
        "within a few days or weeks after being infected with the virus. But others have "
        "post-COVID conditions. They may:&lt;/p&gt;\n"
        "&lt;ul&gt;\n"
        "&lt;li&gt;Have symptoms that linger for weeks, months, or even years&lt;/li&gt; \n"
        "&lt;li&gt;Seem to recover from COVID-19 but then see their symptoms return&lt;/li&gt;\n"
        "&lt;li&gt;Develop new symptoms or new health conditions within a few months of having "
        "COVID-19&lt;/li&gt;\n"
        "&lt;/ul&gt;\n"
        "\n"
        "&lt;p&gt;There are several other names for post-COVID conditions. It is often called "
        "long COVID. But it can also be called long-haul COVID, long-term effects of COVID, "
        "chronic COVID, post-acute COVID-19, and post-acute sequelae of SARS-CoV-2 "
        "(PASC).&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/postcovidconditionslongcovid.html" id="7808" '
        'language="Spanish">Afecciones posteriores al COVID-19 (COVID-19 '
        "persistente)</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000094024">Post-Acute COVID-19 Syndrome</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000086382">COVID-19</descriptor>\n'
        '            <qualifier id="Q000150">complications</qualifier>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181">COVID-19 '
        "(Coronavirus Disease 2019)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/covid19testing.html" '
        'id="7627">COVID-19 Testing</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/covid19vaccines.html" '
        'id="7647">COVID-19 Vaccines</related-topic>\n'
        "          <see-reference>Long COVID</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "  </list>\n"
        "</nlmSearchResult>"
    ),
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=3&rettype=topic&term=zzzzqqqq&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>zzzzqqqq</term>\n"
        "  <count>0</count>\n"
        "</nlmSearchResult>"
    ),
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=myalgicencephalomyelitischronicfatiguesyndrome&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>myalgicencephalomyelitischronicfatiguesyndrome</term>\n"
        "  <file>viv_7JHhxR</file>\n"
        "  <server>pvlb7srch16</server>\n"
        "  <count>3</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <list num="3" start="0" per="10">\n'
        '    <document rank="0" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Myalgic encephalomyelitis/chronic fatigue syndrome '
        "(ME/CFS) is a long-term illness. It causes severe fatigue and many other symptoms. "
        'Learn about managing them." title="Myalgic Encephalomyelitis/Chronic Fatigue Syndrome" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89" language="English" date-created="02/19/1999">\n'
        "          <also-called>CFS</also-called>\n"
        "          <also-called>Chronic fatigue syndrome</also-called>\n"
        "          <also-called>ME/CFS</also-called>\n"
        "          <also-called>Myalgic encephalomyelitis</also-called>\n"
        "          <also-called>SEID</also-called>\n"
        "          <also-called>Systemic exertion intolerance disease</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is myalgic encephalomyelitis/chronic fatigue "
        "syndrome (ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is a serious, "
        "long-term illness that affects many body systems. Another name for it is chronic "
        "fatigue syndrome (CFS). ME/CFS can often make you unable to do your usual activities. "
        "Sometimes you may not even be able to get out of bed.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes myalgic encephalomyelitis/chronic fatigue syndrome "
        "(ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Researchers don't yet know what causes ME/CFS. There may be more than one "
        "potential cause. It is also possible that two or more triggers might work together to "
        "cause the illness.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;Researchers are studying many possible causes, "
        "including:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/bonesjointsandmuscles.html" '
        'id="10">Bones, Joints and Muscles</group>\n'
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="1821" language="Spanish">Encefalomielitis miálgica/Síndrome de fatiga '
        "crónica</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D015673">Fatigue Syndrome, Chronic</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/fatigue.html" '
        'id="5324">Fatigue</related-topic>\n'
        "          <see-reference>CFS</see-reference>\n"
        "          <see-reference>Chronic Fatigue Syndrome</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" url="https://medlineplus.gov/fatigue.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Are you tired? Find out about some of the common and '
        'uncommon causes of fatigue and how to help yourself. " title="Fatigue" '
        'url="https://medlineplus.gov/fatigue.html" id="5324" language="English" '
        'date-created="03/08/2010">\n'
        "          <also-called>Tiredness</also-called>\n"
        "          <also-called>Weariness</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue is a feeling of weariness, tiredness, or lack of energy. It can "
        "interfere with your usual daily activities. Fatigue can be a normal response to "
        "physical activity, emotional &lt;a "
        'href="https://medlineplus.gov/stress.html"&gt;stress&lt;/a&gt;, boredom, or lack of '
        "sleep. But sometimes it can be a sign of a mental or physical condition. If you have "
        "been feeling tired for weeks, contact your health care provider. They can help you "
        "find out what's causing your fatigue and recommend ways to relieve it.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue itself is not a disease; it's a symptom. It can have many different "
        "causes, including &lt;a "
        'href="https://medlineplus.gov/pregnancy.html"&gt;pregnancy&lt;/a&gt; and various '
        "medical problems, treatments, and lifestyle habits such as:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/symptoms.html" id="31">Symptoms</group>\n'
        '          <language-mapped-topic url="https://medlineplus.gov/spanish/fatigue.html" '
        'id="5325" language="Spanish">Fatiga</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D005221">Fatigue</descriptor>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89">Myalgic Encephalomyelitis/Chronic Fatigue Syndrome</related-topic>\n'
        "          <see-reference>Tiredness</see-reference>\n"
        "          <see-reference>Weariness</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Anyone who had COVID-19 can have ongoing symptoms. '
        "Learn about post-COVID conditions (long COVID), including symptoms, diagnosis, "
        'treatments, and prevention." title="Post-COVID Conditions (Long COVID)" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807" '
        'language="English" date-created="09/20/2022">\n'
        "          <also-called>Chronic COVID</also-called>\n"
        "          <also-called>Long-haul COVID</also-called>\n"
        "          <also-called>Long-term effects of COVID</also-called>\n"
        "          <full-summary>&lt;h3&gt;What are post-COVID conditions (long "
        "COVID)?&lt;/h3&gt;\n"
        "&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt; '
        "(coronavirus disease 2019) is an illness caused by a virus. Many people get better "
        "within a few days or weeks after being infected with the virus. But others have "
        "post-COVID conditions. They may:&lt;/p&gt;\n"
        "&lt;ul&gt;\n"
        "&lt;li&gt;Have symptoms that linger for weeks, months, or even years&lt;/li&gt; \n"
        "&lt;li&gt;Seem to recover from COVID-19 but then see their symptoms return&lt;/li&gt;\n"
        "&lt;li&gt;Develop new symptoms or new health conditions within a few months of having "
        "COVID-19&lt;/li&gt;\n"
        "&lt;/ul&gt;\n"
        "\n"
        "&lt;p&gt;There are several other names for post-COVID conditions. It is often called "
        "long COVID. But it can also be called long-haul COVID, long-term effects of COVID, "
        "chronic COVID, post-acute COVID-19, and post-acute sequelae of SARS-CoV-2 "
        "(PASC).&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/postcovidconditionslongcovid.html" id="7808" '
        'language="Spanish">Afecciones posteriores al COVID-19 (COVID-19 '
        "persistente)</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000094024">Post-Acute COVID-19 Syndrome</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000086382">COVID-19</descriptor>\n'
        '            <qualifier id="Q000150">complications</qualifier>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181">COVID-19 '
        "(Coronavirus Disease 2019)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/covid19testing.html" '
        'id="7627">COVID-19 Testing</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/covid19vaccines.html" '
        'id="7647">COVID-19 Vaccines</related-topic>\n'
        "          <see-reference>Long COVID</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "  </list>\n"
        "</nlmSearchResult>"
    ),
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=fatigue&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>fatigue</term>\n"
        "  <file>viv_a9Tsbl</file>\n"
        "  <server>pvlb7srch16</server>\n"
        "  <count>106</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <list num="106" start="0" per="10">\n'
        '    <document rank="1" url="https://medlineplus.gov/fatigue.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Are you tired? Find out about some of the common and '
        'uncommon causes of fatigue and how to help yourself. " title="Fatigue" '
        'url="https://medlineplus.gov/fatigue.html" id="5324" language="English" '
        'date-created="03/08/2010">\n'
        "          <also-called>Tiredness</also-called>\n"
        "          <also-called>Weariness</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue is a feeling of weariness, tiredness, or lack of energy. It can "
        "interfere with your usual daily activities. Fatigue can be a normal response to "
        "physical activity, emotional &lt;a "
        'href="https://medlineplus.gov/stress.html"&gt;stress&lt;/a&gt;, boredom, or lack of '
        "sleep. But sometimes it can be a sign of a mental or physical condition. If you have "
        "been feeling tired for weeks, contact your health care provider. They can help you "
        "find out what's causing your fatigue and recommend ways to relieve it.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes fatigue?&lt;/h3&gt;\n"
        "&lt;p&gt;Fatigue itself is not a disease; it's a symptom. It can have many different "
        "causes, including &lt;a "
        'href="https://medlineplus.gov/pregnancy.html"&gt;pregnancy&lt;/a&gt; and various '
        "medical problems, treatments, and lifestyle habits such as:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/symptoms.html" id="31">Symptoms</group>\n'
        '          <language-mapped-topic url="https://medlineplus.gov/spanish/fatigue.html" '
        'id="5325" language="Spanish">Fatiga</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D005221">Fatigue</descriptor>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89">Myalgic Encephalomyelitis/Chronic Fatigue Syndrome</related-topic>\n'
        "          <see-reference>Tiredness</see-reference>\n"
        "          <see-reference>Weariness</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="0" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Myalgic encephalomyelitis/chronic fatigue syndrome '
        "(ME/CFS) is a long-term illness. It causes severe fatigue and many other symptoms. "
        'Learn about managing them." title="Myalgic Encephalomyelitis/Chronic Fatigue Syndrome" '
        'url="https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="89" language="English" date-created="02/19/1999">\n'
        "          <also-called>CFS</also-called>\n"
        "          <also-called>Chronic fatigue syndrome</also-called>\n"
        "          <also-called>ME/CFS</also-called>\n"
        "          <also-called>Myalgic encephalomyelitis</also-called>\n"
        "          <also-called>SEID</also-called>\n"
        "          <also-called>Systemic exertion intolerance disease</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is myalgic encephalomyelitis/chronic fatigue "
        "syndrome (ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Myalgic encephalomyelitis/chronic fatigue syndrome (ME/CFS) is a serious, "
        "long-term illness that affects many body systems. Another name for it is chronic "
        "fatigue syndrome (CFS). ME/CFS can often make you unable to do your usual activities. "
        "Sometimes you may not even be able to get out of bed.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes myalgic encephalomyelitis/chronic fatigue syndrome "
        "(ME/CFS)?&lt;/h3&gt;\n"
        "&lt;p&gt;Researchers don't yet know what causes ME/CFS. There may be more than one "
        "potential cause. It is also possible that two or more triggers might work together to "
        "cause the illness.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;Researchers are studying many possible causes, "
        "including:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/bonesjointsandmuscles.html" '
        'id="10">Bones, Joints and Muscles</group>\n'
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="1821" language="Spanish">Encefalomielitis miálgica/Síndrome de fatiga '
        "crónica</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D015673">Fatigue Syndrome, Chronic</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/fatigue.html" '
        'id="5324">Fatigue</related-topic>\n'
        "          <see-reference>CFS</see-reference>\n"
        "          <see-reference>Chronic Fatigue Syndrome</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/fibromyalgia.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Fibromyalgia (FMS) is a chronic or long-term '
        "condition characterized by pain and tenderness all over the body. Learn about symptoms "
        'and treatment." title="Fibromyalgia" url="https://medlineplus.gov/fibromyalgia.html" '
        'id="32" language="English" date-created="10/22/1998">\n'
        "          <also-called>FMS</also-called>\n"
        "          <also-called>Fibro</also-called>\n"
        "          <full-summary>&lt;p&gt;Fibromyalgia is chronic (long-lasting) condition that "
        'causes &lt;a href="https://medlineplus.gov/chronicpain.html"&gt;pain&lt;/a&gt; all '
        'over the body, &lt;a href="https://medlineplus.gov/fatigue.html"&gt;fatigue&lt;/a&gt;, '
        "and other symptoms. There is no cure, but treatments can help with the "
        "symptoms.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes fibromyalgia?&lt;/h3&gt;\n"
        "&lt;p&gt;The exact cause of fibromyalgia is unknown. Studies of the brains of people "
        "with fibromyalgia found that they seem to process pain differently than people who "
        "don't have it. They may feel pain when others do not, and they may also have a more "
        "severe reaction to pain.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;Fibromyalgia can run in families, so &lt;a "
        'href="https://medlineplus.gov/genetics/condition/fibromyalgia"&gt;genetics&lt;/a&gt; '
        "may also play a role. Other factors may also be involved, such as having certain "
        "diseases that cause pain.&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/bonesjointsandmuscles.html" '
        'id="10">Bones, Joints and Muscles</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/fibromyalgia.html" id="1903" '
        'language="Spanish">Fibromialgia</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D005356">Fibromyalgia</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.niams.nih.gov/">National Institute of '
        "Arthritis and Musculoskeletal and Skin Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/arthritis.html" '
        'id="23">Arthritis</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/muscledisorders.html" '
        'id="510">Muscle Disorders</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/pain.html" '
        'id="351">Pain</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "    </list>\n"
        "</nlmSearchResult>"
    ),
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopicsSpanish&retmax=10&rettype=topic&term=fatigue&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>fatigue</term>\n"
        "  <file>viv_FkG3Nk</file>\n"
        "  <server>pvlb7srch15</server>\n"
        "  <count>74</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <list num="74" start="0" per="10">\n'
        '    <document rank="0" url="https://medlineplus.gov/spanish/fatigue.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Todo el mundo se siente cansado de vez en cuando. '
        'Entérese cuándo es solo cansancio y cuándo es fatiga aquí." title="Fatiga" '
        'url="https://medlineplus.gov/spanish/fatigue.html" id="5325" language="Spanish" '
        'date-created="06/21/2010">\n'
        "          <also-called>Cansancio extremo</also-called>\n"
        "          <full-summary>&lt;h3&gt;¿Qué es la fatiga?&lt;/h3&gt;\n"
        "&lt;p&gt;La fatiga es una sensación de cansancio, agotamiento o falta de energía. "
        "Puede interferir con sus actividades diarias habituales. La fatiga puede ser una "
        "respuesta normal a la actividad física, el &lt;a "
        'href="https://medlineplus.gov/spanish/stress.html"&gt;estrés&lt;/a&gt; emocional, el '
        "aburrimiento o la falta de sueño. Pero a veces puede ser un signo de un problema "
        "físico o mental. Si se siente cansado durante semanas, hable con su profesional de la "
        "salud. Éste puede ayudarle a encontrar la causa de su fatiga y recomendarle formas de "
        "aliviarla.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;¿Qué causa la fatiga?&lt;/h3&gt;\n"
        "&lt;p&gt;La fatiga en sí misma no es una enfermedad, es un síntoma. Puede tener muchas "
        "causas diferentes, incluyendo el &lt;a "
        'href="https://medlineplus.gov/spanish/pregnancy.html"&gt;embarazo&lt;/a&gt; y diversos '
        "problemas médicos, tratamientos y hábitos de estilo de vida "
        "como:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/spanish/symptoms.html" '
        'id="31">Síntomas</group>\n'
        '          <language-mapped-topic url="https://medlineplus.gov/fatigue.html" id="5324" '
        'language="English">Fatigue</language-mapped-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/spanish/myalgicencephalomyelitischronicfatiguesyndrome.html" '
        'id="1821">Encefalomielitis miálgica/Síndrome de fatiga crónica</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" '
        'url="https://medlineplus.gov/spanish/postcovidconditionslongcovid.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Cualquier persona que haya tenido COVID-19, ya sea '
        "grave o leve, puede tener síntomas persistentes. Entérese sobre síntomas, diagnóstico, "
        'tratamientos y prevención de las afecciones posteriores al COVID (COVID persistente)." '
        'title="Afecciones posteriores al COVID-19 (COVID-19 persistente)" '
        'url="https://medlineplus.gov/spanish/postcovidconditionslongcovid.html" id="7808" '
        'language="Spanish" date-created="09/20/2022">\n'
        "          <also-called>COVID-19 crónico</also-called>\n"
        "          <also-called>COVID-19 de larga duración</also-called>\n"
        "          <also-called>Condición post-COVID-19</also-called>\n"
        "          <also-called>Síndrome del COVID-19 persistente</also-called>\n"
        "          <also-called>Síndrome post-COVID-19</also-called>\n"
        "          <full-summary>&lt;h3&gt;¿Qué son las afecciones posteriores al COVID (COVID "
        "persistente)?&lt;/h3&gt;\n"
        "&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/spanish/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt; '
        "(enfermedad por coronavirus 2019) es una afección causada por un virus. Muchas "
        "personas mejoran a los pocos días o semanas de haberse infectado con el virus. Pero "
        "otras tienen afecciones post-COVID. Estas pueden:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/spanish/infections.html" '
        'id="12">Infecciones</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807" '
        'language="English">Post-COVID Conditions (Long COVID)</language-mapped-topic>\n'
        "          <see-reference>COVID persistente</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/spanish/aplasticanemia.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="La anemia aplásica es un trastorno raro en que la '
        "médula espinal no produce suficientes células nuevas. Síntomas y tratamientos de la "
        'anemia aplásica. " title="Anemia aplásica" '
        'url="https://medlineplus.gov/spanish/aplasticanemia.html" id="5956" language="Spanish" '
        'date-created="01/09/2012">\n'
        "          <full-summary>&lt;h3&gt;¿Qué es la anemia aplásica?&lt;/h3&gt;\n"
        "&lt;p&gt;La &lt;a "
        'href="https://medlineplus.gov/spanish/anemia.html"&gt;anemia&lt;/a&gt; aplásica es un '
        "trastorno sanguíneo poco común pero grave. Si lo tiene, su &lt;a "
        'href="https://medlineplus.gov/spanish/bonemarrowdiseases.html"&gt;médula '
        "ósea&lt;/a&gt; no produce suficientes células sanguíneas nuevas. Ocurre cuando hay "
        "daño a las células madre dentro de la médula ósea. Existen diferentes tipos de anemia "
        "aplásica, incluyendo la anemia de Fanconi.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;¿Qué causa la anemia aplásica?&lt;/h3&gt;\n"
        "&lt;p&gt;Las causas de la anemia aplásica pueden incluir:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/spanish/bloodheartandcirculation.html" '
        'id="7">Sangre, corazón y circulación</group>\n'
        '          <group url="https://medlineplus.gov/spanish/immunesystem.html" '
        'id="22">Sistema inmunitario</group>\n'
        '          <language-mapped-topic url="https://medlineplus.gov/aplasticanemia.html" '
        'id="5955" language="English">Aplastic Anemia</language-mapped-topic>\n'
        "          <primary-institute "
        'url="https://medlineplus.gov/spanish/nihinstitutes.html#NHLBI">Instituto Nacional del '
        "Corazón, los Pulmones y la Sangre</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/spanish/anemia.html" '
        'id="1743">Anemia</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/spanish/bonemarrowdiseases.html" '
        'id="1781">Enfermedades de la médula ósea</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/spanish/bonemarrowtransplantation.html" '
        'id="1782">Trasplante de médula ósea</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "    </list>\n"
        "</nlmSearchResult>"
    ),
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=G93.32&mainSearchCriteria.v.cs=2.16.840.1.113883.6.90": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:08Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {
                "type": "text",
                "_value": "MedlinePlus Connect results for ICD-10-CM G93.32",
            },
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "G93.32"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "ICD10CM"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [
                {
                    "title": {
                        "_value": "Myalgic Encephalomyelitis/Chronic Fatigue Syndrome",
                        "type": "text",
                    },
                    "link": [
                        {
                            "href": "https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/myalgicencephalomyelitischronicfatiguesyndrome.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h3>What is myalgic "
                        "encephalomyelitis/chronic fatigue syndrome "
                        "(ME/CFS)?</h3>\n"
                        "<p>Myalgic encephalomyelitis/chronic fatigue "
                        "syndrome (ME/CFS) is a serious, long-term "
                        "illness that affects many body systems. "
                        "Another name for it is chronic fatigue "
                        "syndrome (CFS). ME/CFS can often make you "
                        "unable to do your usual activities. "
                        "Sometimes you may not even be able to get "
                        "out of bed.</p>\n"
                        "\n"
                        "<h3>What causes myalgic "
                        "encephalomyelitis/chronic fatigue syndrome "
                        "(ME/CFS)?</h3>\n"
                        "<p>Researchers don't yet know what causes "
                        "ME/CFS. There may be more than one potential "
                        "cause. It is also possible that two or more "
                        "triggers might work together to cause the "
                        "illness.</p>\n"
                        "\n"
                        "<p>Researchers are studying many possible "
                        "causes, including:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:08Z"},
                }
            ],
        }
    },
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=G93.31&mainSearchCriteria.v.cs=2.16.840.1.113883.6.90": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:08Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {
                "type": "text",
                "_value": "MedlinePlus Connect results for ICD-10-CM G93.31",
            },
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "G93.31"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "ICD10CM"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [
                {
                    "title": {"_value": "Fatigue", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/fatigue.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/fatigue.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h3>What is fatigue?</h3>\n"
                        "<p>Fatigue is a feeling of weariness, "
                        "tiredness, or lack of energy. It can "
                        "interfere with your usual daily activities. "
                        "Fatigue can be a normal response to physical "
                        "activity, emotional <a "
                        'href="https://medlineplus.gov/stress.html?utm_source=mplusconnect">stress</a>, '
                        "boredom, or lack of sleep. But sometimes it "
                        "can be a sign of a mental or physical "
                        "condition. If you have been feeling tired "
                        "for weeks, contact your health care "
                        "provider. They can help you find out what's "
                        "causing your fatigue and recommend ways to "
                        "relieve it.</p>\n"
                        "\n"
                        "<h3>What causes fatigue?</h3>\n"
                        "<p>Fatigue itself is not a disease; it's a "
                        "symptom. It can have many different causes, "
                        "including <a "
                        'href="https://medlineplus.gov/pregnancy.html?utm_source=mplusconnect">pregnancy</a> '
                        "and various medical problems, treatments, "
                        "and lifestyle habits such as:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:08Z"},
                },
                {
                    "title": {"_value": "Neurologic Diseases", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/neurologicdiseases.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/neurologicdiseases.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<p>The brain, spinal cord, and nerves make "
                        "up the nervous system. Together they control "
                        "all the workings of the body. When something "
                        "goes wrong with a part of your nervous "
                        "system, you can have trouble moving, "
                        "speaking, swallowing, breathing, or "
                        "learning.  You can also have problems with "
                        "your memory, senses, or mood.</p>\n"
                        "\n"
                        "<p>There are more than 600 neurologic "
                        "diseases. Major types include:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:08Z"},
                },
                {
                    "title": {"_value": "Viral Infections", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/viralinfections.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/viralinfections.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h3>What are viruses?</h3>\n"
                        "<p>Viruses are very tiny germs. They are "
                        "made of genetic material (either <a "
                        'href="https://medlineplus.gov/genetics/understanding/basics/dna/?utm_source=mplusconnect">DNA</a>  '
                        "or RNA) inside of a protein coating. There "
                        "are a huge number of viruses on earth. Only "
                        "a small number of them can infect humans. "
                        "Those viruses can infect our cells, which "
                        "may cause disease. Some of the diseases that "
                        "viruses can cause include the <a "
                        'href="https://medlineplus.gov/commoncold.html?utm_source=mplusconnect">common '
                        "cold</a>, the <a "
                        'href="https://medlineplus.gov/flu.html?utm_source=mplusconnect">flu</a>, '
                        "<a "
                        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html?utm_source=mplusconnect">COVID-19</a>, '
                        "and <a "
                        'href="https://medlineplus.gov/hiv.html?utm_source=mplusconnect">HIV</a>.</p>\n'
                        "\n"
                        "\n"
                        "<h3>How are viruses spread?</h3>\n"
                        "<p>Viruses can be spread in different "
                        "ways:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:08Z"},
                },
            ],
        }
    },
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=neurologicdiseases&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>neurologicdiseases</term>\n"
        "  <file>viv_vLbhwX</file>\n"
        "  <server>pvlb7srch15</server>\n"
        "  <count>17</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <spellingCorrection>"neurologic diseases"</spellingCorrection>\n'
        '  <list num="17" start="0" per="10">\n'
        '    <document rank="0" url="https://medlineplus.gov/neurologicdiseases.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Your nervous system includes your brain, spinal cord, '
        "and nerves. Learn about neurologic diseases, including their symptoms, causes, and "
        'treatments." title="Neurologic Diseases" '
        'url="https://medlineplus.gov/neurologicdiseases.html" id="341" language="English" '
        'date-created="01/05/2000">\n'
        "          <also-called>Nervous system diseases</also-called>\n"
        "          <full-summary>&lt;p&gt;The brain, spinal cord, and nerves make up the "
        "nervous system. Together they control all the workings of the body. When something "
        "goes wrong with a part of your nervous system, you can have trouble moving, speaking, "
        "swallowing, breathing, or learning.  You can also have problems with your memory, "
        "senses, or mood.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;There are more than 600 neurologic diseases. Major types "
        "include:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/brainandnerves.html" id="14">Brain and '
        "Nerves</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/neurologicdiseases.html" id="2053" '
        'language="Spanish">Enfermedades neurológicas</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D009422">Nervous System Diseases</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/acuteflaccidmyelitis.html" '
        'id="7207">Acute Flaccid Myelitis</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/autonomicnervoussystemdisorders.html" id="4242">Autonomic '
        "Nervous System Disorders</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/braindiseases.html" '
        'id="174">Brain Diseases</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/complexregionalpainsyndrome.html" id="382">Complex '
        "Regional Pain Syndrome</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/degenerativenervediseases.html" '
        'id="619">Degenerative Nerve Diseases</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/epilepsy.html" '
        'id="244">Epilepsy</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/meningitis.html" '
        'id="324">Meningitis</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/movementdisorders.html" '
        'id="520">Movement Disorders</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/neuromusculardisorders.html" '
        'id="1518">Neuromuscular Disorders</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/parkinsonsdisease.html" '
        'id="85">Parkinson\'s Disease</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/peripheralnervedisorders.html" '
        'id="1095">Peripheral Nerve Disorders</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/spinalcorddiseases.html" '
        'id="410">Spinal Cord Diseases</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/tourettesyndrome.html" '
        'id="442">Tourette Syndrome</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/trigeminalneuralgia.html" '
        'id="2729">Trigeminal Neuralgia</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/vonhippellindaudisease.html" '
        'id="4361">Von Hippel-Lindau Disease</related-topic>\n'
        "          <see-reference>Nerve Diseases</see-reference>\n"
        "          <see-reference>Nervous System Diseases</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" url="https://medlineplus.gov/acuteflaccidmyelitis.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Acute flaccid myelitis (AFM) is a rare but serious '
        "neurologic disease. It mostly affects children. Learn about its possible causes and "
        'symptoms." title="Acute Flaccid Myelitis" '
        'url="https://medlineplus.gov/acuteflaccidmyelitis.html" id="7207" language="English" '
        'date-created="11/01/2018">\n'
        "          <also-called>AFM</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is acute flaccid myelitis (AFM)?&lt;/h3&gt;\n"
        "&lt;p&gt;Acute flaccid myelitis (AFM) is a &lt;a "
        'href="https://medlineplus.gov/neurologicdiseases.html"&gt;neurologic '
        "disease&lt;/a&gt;. It is rare, but serious. It affects an area of the spinal cord "
        "called gray matter. This can cause the muscles and reflexes in the body to become "
        "weak.&lt;/p&gt;\n"
        "\n"
        '&lt;p&gt;Because of these symptoms, some people call AFM a "polio-like" illness. But '
        "it is different from &lt;a "
        'href="https://medlineplus.gov/polioandpostpoliosyndrome.html"&gt;polio&lt;/a&gt;. AFM '
        "is not caused by polioviruses.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes acute flaccid myelitis (AFM)?&lt;/h3&gt;\n"
        "&lt;p&gt;AFM can be caused by several different viruses. Researchers think that "
        "enteroviruses have been causing the recent increases in the number of children with "
        "AFM. AFM can also be caused by other viruses, including flaviviruses, herpesviruses, "
        "and adenoviruses.&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/childrenandteenagers.html" '
        'id="3">Children and Teenagers</group>\n'
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/brainandnerves.html" id="14">Brain and '
        "Nerves</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/acuteflaccidmyelitis.html" id="7208" '
        'language="Spanish">Mielitis flácida aguda</language-mapped-topic>\n'
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/aphasia.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Aphasia is a disorder caused by damage to the parts '
        "of the brain that control language. It can make it hard for you to read, write, and "
        'speak. " title="Aphasia" url="https://medlineplus.gov/aphasia.html" id="1212" '
        'language="English" date-created="02/22/2000">\n'
        "          <full-summary>&lt;h3&gt;What is aphasia?&lt;/h3&gt;\n"
        "&lt;p&gt;Aphasia is a language disorder that makes it hard for you to read, write, and "
        "say what you mean to say. Sometimes it makes it hard to understand what other people "
        "are saying, too. Aphasia is not a disease. It's a symptom of damage to the parts of "
        "the brain that control language.&lt;/p&gt;\n"
        "  \n"
        "&lt;p&gt;The signs of aphasia depend on which part of the brain is damaged. There are "
        "four main types of aphasia:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/brainandnerves.html" id="14">Brain and '
        "Nerves</group>\n"
        '          <language-mapped-topic url="https://medlineplus.gov/spanish/aphasia.html" '
        'id="1753" language="Spanish">Afasia</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D001037">Aphasia</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="https://www.nidcd.nih.gov/">National Institute on '
        "Deafness and Other Communication Disorders</primary-institute>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/speechandcommunicationdisorders.html" id="409">Speech and '
        "Communication Disorders</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/stroke.html" '
        'id="8">Stroke</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "    </list>\n"
        "</nlmSearchResult>"
    ),
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=viralinfections&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>viralinfections</term>\n"
        "  <file>viv_Q4vxJ6</file>\n"
        "  <server>pvlb7srch16</server>\n"
        "  <count>29</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <spellingCorrection>"viral infections"</spellingCorrection>\n'
        '  <list num="29" start="0" per="10">\n'
        '    <document rank="0" url="https://medlineplus.gov/viralinfections.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Viruses cause familiar infections such as the common '
        "cold, but they also cause severe illnesses. Learn more about viral infections and "
        'their symptoms." title="Viral Infections" '
        'url="https://medlineplus.gov/viralinfections.html" id="454" language="English" '
        'date-created="10/01/1999">\n'
        "          <full-summary>&lt;h3&gt;What are viruses?&lt;/h3&gt;\n"
        "&lt;p&gt;Viruses are very tiny germs. They are made of genetic material (either &lt;a "
        'href="https://medlineplus.gov/genetics/understanding/basics/dna/"&gt;DNA&lt;/a&gt;  or '
        "RNA) inside of a protein coating. There are a huge number of viruses on earth. Only a "
        "small number of them can infect humans. Those viruses can infect our cells, which may "
        "cause disease. Some of the diseases that viruses can cause include the &lt;a "
        'href="https://medlineplus.gov/commoncold.html"&gt;common cold&lt;/a&gt;, the &lt;a '
        'href="https://medlineplus.gov/flu.html"&gt;flu&lt;/a&gt;, &lt;a '
        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt;, '
        'and &lt;a href="https://medlineplus.gov/hiv.html"&gt;HIV&lt;/a&gt;.&lt;/p&gt;\n'
        "\n"
        "\n"
        "&lt;h3&gt;How are viruses spread?&lt;/h3&gt;\n"
        "&lt;p&gt;Viruses can be spread in different ways:&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/immunesystem.html" id="22">Immune '
        "System</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/viralinfections.html" id="2221" '
        'language="Spanish">Infecciones virales</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D014777">Virus Diseases</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.niaid.nih.gov/">National Institute of '
        "Allergy and Infectious Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/acuteflaccidmyelitis.html" '
        'id="7207">Acute Flaccid Myelitis</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/chickenpox.html" '
        'id="182">Chickenpox</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/chikungunya.html" '
        'id="6345">Chikungunya</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/commoncold.html" id="196">Common '
        "Cold</related-topic>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181">COVID-19 '
        "(Coronavirus Disease 2019)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/croup.html" '
        'id="6292">Croup</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/cytomegalovirusinfections.html" '
        'id="3980">Cytomegalovirus Infections</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/dengue.html" '
        'id="3104">Dengue</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/ebola.html" '
        'id="6202">Ebola</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/fifthdisease.html" '
        'id="1609">Fifth Disease</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/flu.html" '
        'id="299">Flu</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hantavirusinfections.html" '
        'id="3217">Hantavirus Infections</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hemorrhagicfevers.html" '
        'id="1652">Hemorrhagic Fevers</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hepatitisa.html" '
        'id="1686">Hepatitis A</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hepatitisb.html" '
        'id="1687">Hepatitis B</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hepatitisc.html" '
        'id="1286">Hepatitis C</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/herpessimplex.html" '
        'id="286">Herpes Simplex</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hiv.html" '
        'id="1">HIV</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hpv.html" '
        'id="1715">HPV</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/infectiousmononucleosis.html" '
        'id="298">Infectious Mononucleosis</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/measles.html" '
        'id="318">Measles</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/mpox.html" '
        'id="3229">Mpox</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/mumps.html" '
        'id="334">Mumps</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/norovirusinfections.html" '
        'id="6103">Norovirus Infections</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/polioandpostpoliosyndrome.html" '
        'id="365">Polio and Post-Polio Syndrome</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/rabies.html" '
        'id="523">Rabies</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/respiratorysyncytialvirusinfections.html" '
        'id="3101">Respiratory Syncytial Virus Infections</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/rotavirusinfections.html" '
        'id="3215">Rotavirus Infections</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/rubella.html" '
        'id="387">Rubella</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/shingles.html" '
        'id="90">Shingles</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/vaccines.html" '
        'id="294">Vaccines</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/warts.html" '
        'id="459">Warts</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/westnilevirus.html" '
        'id="1377">West Nile Virus</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/zikavirus.html" id="6342">Zika '
        "Virus</related-topic>\n"
        "          <see-reference>Adenovirus Infections</see-reference>\n"
        "          <see-reference>Coxsackievirus Infections</see-reference>\n"
        "          <see-reference>Enterovirus</see-reference>\n"
        "          <see-reference>Hand, Foot, and Mouth Disease</see-reference>\n"
        "          <see-reference>Infections, Viral</see-reference>\n"
        "          <see-reference>Roseola</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" url="https://medlineplus.gov/acuteflaccidmyelitis.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Acute flaccid myelitis (AFM) is a rare but serious '
        "neurologic disease. It mostly affects children. Learn about its possible causes and "
        'symptoms." title="Acute Flaccid Myelitis" '
        'url="https://medlineplus.gov/acuteflaccidmyelitis.html" id="7207" language="English" '
        'date-created="11/01/2018">\n'
        "          <also-called>AFM</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is acute flaccid myelitis (AFM)?&lt;/h3&gt;\n"
        "&lt;p&gt;Acute flaccid myelitis (AFM) is a &lt;a "
        'href="https://medlineplus.gov/neurologicdiseases.html"&gt;neurologic '
        "disease&lt;/a&gt;. It is rare, but serious. It affects an area of the spinal cord "
        "called gray matter. This can cause the muscles and reflexes in the body to become "
        "weak.&lt;/p&gt;\n"
        "\n"
        '&lt;p&gt;Because of these symptoms, some people call AFM a "polio-like" illness. But '
        "it is different from &lt;a "
        'href="https://medlineplus.gov/polioandpostpoliosyndrome.html"&gt;polio&lt;/a&gt;. AFM '
        "is not caused by polioviruses.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What causes acute flaccid myelitis (AFM)?&lt;/h3&gt;\n"
        "&lt;p&gt;AFM can be caused by several different viruses. Researchers think that "
        "enteroviruses have been causing the recent increases in the number of children with "
        "AFM. AFM can also be caused by other viruses, including flaviviruses, herpesviruses, "
        "and adenoviruses.&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/childrenandteenagers.html" '
        'id="3">Children and Teenagers</group>\n'
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/brainandnerves.html" id="14">Brain and '
        "Nerves</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/acuteflaccidmyelitis.html" id="7208" '
        'language="Spanish">Mielitis flácida aguda</language-mapped-topic>\n'
        '          <primary-institute url="http://www.ninds.nih.gov/">National Institute of '
        "Neurological Disorders and Stroke</primary-institute>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/antibioticresistance.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Antibiotics can save lives. But when they are not '
        "used properly they can become less effective. Use them only when necessary to combat "
        'antibiotic resistance." title="Antibiotic Resistance" '
        'url="https://medlineplus.gov/antibioticresistance.html" id="6252" language="English" '
        'date-created="05/19/2015">\n'
        "          <full-summary>&lt;h3&gt;What are antibiotics?&lt;/h3&gt;\n"
        "&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/antibiotics.html"&gt;Antibiotics&lt;/a&gt; are medicines '
        'that treat &lt;a href="https://medlineplus.gov/bacterialinfections.html"&gt;bacterial '
        "infections&lt;/a&gt; in humans and animals. They work by killing the bacteria or "
        "making it hard for the bacteria to grow and multiply. When used properly, antibiotics "
        "can save lives. But there is a growing problem of antibiotic resistance.&lt;/p&gt;\n"
        "\n"
        "&lt;h3&gt;What is antibiotic resistance?&lt;/h3&gt;\n"
        "&lt;p&gt;Antibiotic resistance happens when bacteria change and can resist the effects "
        "of an antibiotic. The bacteria are not killed, and they continue to grow. The "
        "infections these bacteria cause are called resistant infections. Resistant infections "
        "can be difficult, and sometimes impossible, to treat. In some cases, they can even be "
        "deadly. &lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/drugtherapy.html" id="36">Drug '
        "Therapy</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/antibioticresistance.html" id="6253" '
        'language="Spanish">Resistencia a los antibióticos</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D024881">Drug Resistance, Bacterial</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D004352">Drug Resistance, Microbial</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.niaid.nih.gov/">National Institute of '
        "Allergy and Infectious Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/antibiotics.html" '
        'id="222">Antibiotics</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/bacterialinfections.html" '
        'id="158">Bacterial Infections</related-topic>\n'
        "          <see-reference>Antimicrobial Resistance</see-reference>\n"
        "          <see-reference>VRE</see-reference>\n"
        "          <see-reference>Vancomycin-Resistant Enterococci</see-reference>\n"
        "          <see-reference>Vancomycin-Resistant Staphylococcus aureus</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "    </list>\n"
        "</nlmSearchResult>"
    ),
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=52702003&mainSearchCriteria.v.cs=2.16.840.1.113883.6.96": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:10Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {
                "type": "text",
                "_value": "MedlinePlus Connect results for SNOMED CT 52702003",
            },
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "52702003"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "SNOMEDCT"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [
                {
                    "title": {
                        "_value": "Myalgic Encephalomyelitis/Chronic Fatigue Syndrome",
                        "type": "text",
                    },
                    "link": [
                        {
                            "href": "https://medlineplus.gov/myalgicencephalomyelitischronicfatiguesyndrome.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/myalgicencephalomyelitischronicfatiguesyndrome.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h3>What is myalgic "
                        "encephalomyelitis/chronic fatigue syndrome "
                        "(ME/CFS)?</h3>\n"
                        "<p>Myalgic encephalomyelitis/chronic fatigue "
                        "syndrome (ME/CFS) is a serious, long-term "
                        "illness that affects many body systems. "
                        "Another name for it is chronic fatigue "
                        "syndrome (CFS). ME/CFS can often make you "
                        "unable to do your usual activities. "
                        "Sometimes you may not even be able to get "
                        "out of bed.</p>\n"
                        "\n"
                        "<h3>What causes myalgic "
                        "encephalomyelitis/chronic fatigue syndrome "
                        "(ME/CFS)?</h3>\n"
                        "<p>Researchers don't yet know what causes "
                        "ME/CFS. There may be more than one potential "
                        "cause. It is also possible that two or more "
                        "triggers might work together to cause the "
                        "illness.</p>\n"
                        "\n"
                        "<p>Researchers are studying many possible "
                        "causes, including:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:10Z"},
                }
            ],
        }
    },
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=2951-2&mainSearchCriteria.v.cs=2.16.840.1.113883.6.1": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:11Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {"type": "text", "_value": "MedlinePlus Connect results for LOINC 2951-2"},
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "2951-2"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "LOINC"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [
                {
                    "title": {"_value": "Electrolyte Panel", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/lab-tests/electrolyte-panel?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, 2026-08-10:/lab-tests/electrolyte-panel"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h2>What is an electrolyte panel?</h2>\n"
                        '<p><a data-tid="4224" '
                        'href="https://medlineplus.gov/fluidandelectrolytebalance.html?utm_source=mplusconnect">Electrolytes</a> '
                        'are <a data-tid="4298" '
                        'href="https://medlineplus.gov/minerals.html?utm_source=mplusconnect">minerals</a> '
                        "that have an electrical charge when they are "
                        "dissolved in water or body fluids. You have "
                        "electrolytes in your blood, urine, tissues, "
                        "and other body fluids. They are important "
                        "because they help:</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:11Z"},
                },
                {
                    "title": {"_value": "Sodium Blood Test", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/lab-tests/sodium-blood-test?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, 2026-08-10:/lab-tests/sodium-blood-test"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h2>What is a sodium blood test?</h2>\n"
                        "<p>A sodium blood test measures the amount "
                        'of <a data-tid="3666" '
                        'href="https://medlineplus.gov/sodium.html?utm_source=mplusconnect">sodium</a> '
                        "in your blood. Sodium is a type of <a "
                        'data-tid="4224" '
                        'href="https://medlineplus.gov/fluidandelectrolytebalance.html?utm_source=mplusconnect">electrolyte</a>. '
                        'Electrolytes are <a data-tid="4298" '
                        'href="https://medlineplus.gov/minerals.html?utm_source=mplusconnect">minerals</a>\xa0'
                        "that have an electrical charge when they are "
                        "dissolved in water or body fluids. You have "
                        "electrolytes in your blood, urine (pee), "
                        "tissues, and other body fluids. They help "
                        "control the amount of fluid and the balance "
                        "of acids and bases (pH balance) in your "
                        "body. Sodium also helps your nerves and "
                        "muscles work properly.</p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:11Z"},
                },
            ],
        }
    },
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=861004&mainSearchCriteria.v.cs=2.16.840.1.113883.6.88": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:12Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {"type": "text", "_value": "MedlinePlus Connect results for RXCUI 861004"},
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "861004"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "RXNORM"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [
                {
                    "title": {"_value": "Metformin", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/druginfo/meds/a696005.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/druginfo/meds/a696005.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "Metformin is used alone or with other "
                        "medications, including insulin, to treat "
                        "type 2 diabetes (condition in which the body "
                        "does not use insulin normally and, "
                        "therefore, cannot control the amount of "
                        "sugar in the blood). Metformin is in a class "
                        "of drugs called biguanides. Metformin helps "
                        "to control the amount of glucose (sugar) in "
                        "your blood. It decreases the amount of "
                        "glucose you absorb from your food and the "
                        "amount of glucose made by your liver. "
                        "Metformin also increases your body's "
                        "response to insulin, a natural substance "
                        "that controls the amount of glucose in the "
                        "blood. Metformin is not used to treat type 1 "
                        "diabetes (condition in which the body does "
                        "not produce insulin and therefore cannot "
                        "control the amount of sugar in the blood). "
                        "Over time, people who have diabetes and high "
                        "blood sugar can develop serious or "
                        "life-threatening complications, including "
                        "heart disease, stroke, kidney prob",
                    },
                    "updated": {"_value": "2026-10-08T13:38:12Z"},
                },
                {
                    "title": {"_value": "Diabetes Medicines", "type": "text"},
                    "link": [
                        {
                            "href": "https://medlineplus.gov/diabetesmedicines.html?utm_source=mplusconnect&utm_medium=service",
                            "rel": "alternate",
                        }
                    ],
                    "id": {
                        "_value": "tag: medlineplus.gov, "
                        "2026-08-10:/diabetesmedicines.html?utm_source=mplusconnect&utm_medium=application"
                    },
                    "summary": {
                        "type": "html",
                        "_value": "<h3>What is diabetes?</h3>\n"
                        "<p><a "
                        'href="https://medlineplus.gov/diabetes.html?utm_source=mplusconnect">Diabetes</a> '
                        "is a disease in which your blood glucose, or "
                        "<a "
                        'href="https://medlineplus.gov/bloodglucose.html?utm_source=mplusconnect">blood '
                        "sugar</a>, levels are too high. Glucose "
                        "comes from the foods you eat. The cells of "
                        "your body need glucose for energy. A hormone "
                        "called insulin helps the glucose get into "
                        "your cells.</p> \n"
                        "\n"
                        "With <a "
                        'href="https://medlineplus.gov/diabetestype1.html?utm_source=mplusconnect">type '
                        "1 diabetes</a>, your body does not make "
                        "insulin. With <a "
                        'href="https://medlineplus.gov/diabetestype2.html?utm_source=mplusconnect">type '
                        "2 diabetes</a>,your body does not make or "
                        "use insulin well. Without enough insulin, "
                        "glucose can't get into your cells as quickly "
                        "as usual. The glucose builds up in your "
                        "blood and causes high blood sugar "
                        "levels.<p></p>",
                    },
                    "updated": {"_value": "2026-10-08T13:38:12Z"},
                },
            ],
        }
    },
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=diabetesmedicines&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>diabetesmedicines</term>\n"
        "  <file>viv_nf9kyL</file>\n"
        "  <server>pvlb7srch16</server>\n"
        "  <count>13</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <spellingCorrection>"diabetes medicines"</spellingCorrection>\n'
        '  <list num="13" start="0" per="10">\n'
        '    <document rank="0" url="https://medlineplus.gov/diabetesmedicines.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Diabetes medicines can help to control your Diabetes. '
        'The right medicines depend on factors such as the type of Diabetes you have." '
        'title="Diabetes Medicines" url="https://medlineplus.gov/diabetesmedicines.html" '
        'id="4935" language="English" date-created="02/26/2009">\n'
        "          <full-summary>&lt;h3&gt;What is diabetes?&lt;/h3&gt;\n"
        '&lt;p&gt;&lt;a href="https://medlineplus.gov/diabetes.html"&gt;Diabetes&lt;/a&gt; is a '
        "disease in which your blood glucose, or &lt;a "
        'href="https://medlineplus.gov/bloodglucose.html"&gt;blood sugar&lt;/a&gt;, levels are '
        "too high. Glucose comes from the foods you eat. The cells of your body need glucose "
        "for energy. A hormone called insulin helps the glucose get into your "
        "cells.&lt;/p&gt; \n"
        "\n"
        'With &lt;a href="https://medlineplus.gov/diabetestype1.html"&gt;type 1 '
        "diabetes&lt;/a&gt;, your body does not make insulin. With &lt;a "
        'href="https://medlineplus.gov/diabetestype2.html"&gt;type 2 diabetes&lt;/a&gt;,your '
        "body does not make or use insulin well. Without enough insulin, glucose can't get into "
        "your cells as quickly as usual. The glucose builds up in your blood and causes high "
        "blood sugar levels.&lt;p&gt;&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/endocrinesystem.html" id="23">Endocrine '
        "System</group>\n"
        '          <group url="https://medlineplus.gov/drugtherapy.html" id="36">Drug '
        "Therapy</group>\n"
        '          <group url="https://medlineplus.gov/diabetesmellitus.html" id="45">Diabetes '
        "Mellitus</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/diabetesmedicines.html" id="4936" '
        'language="Spanish">Medicinas para la diabetes</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D061385">Insulins</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D007004">Hypoglycemic Agents</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D007328">Insulin</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="https://www.niddk.nih.gov">National Institute of '
        "Diabetes and Digestive and Kidney Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/bloodglucose.html" '
        'id="6121">Blood Glucose</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetes.html" '
        'id="4">Diabetes</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetesinchildrenandteens.html" '
        'id="6026">Diabetes in Children and Teens</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetestype1.html" '
        'id="1339">Diabetes Type 1</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetestype2.html" '
        'id="5930">Diabetes Type 2</related-topic>\n'
        "          <see-reference>Hypoglycemic Medicines</see-reference>\n"
        "          <see-reference>Insulin</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" url="https://medlineplus.gov/bloodglucose.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Your body processes the food you eat into glucose. '
        "Your blood carries glucose (blood sugar) to all of your body's cells to use for "
        'energy. Learn more." title="Blood Glucose" '
        'url="https://medlineplus.gov/bloodglucose.html" id="6121" language="English" '
        'date-created="04/08/2013">\n'
        "          <also-called>Blood sugar</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is blood glucose?&lt;/h3&gt;\n"
        "&lt;p&gt;Blood glucose, or blood sugar, is the main sugar found in your blood. It is "
        "your body's primary source of energy. It comes from the food you eat. Your body breaks "
        "down most of that food into glucose and releases it into your bloodstream. When your "
        "blood glucose goes up, it signals your pancreas to release insulin. Insulin is a "
        "hormone that helps the glucose get into your cells to be used for "
        "energy.&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/endocrinesystem.html" id="23">Endocrine '
        "System</group>\n"
        '          <group url="https://medlineplus.gov/metabolicproblems.html" '
        'id="40">Metabolic Problems</group>\n'
        '          <group url="https://medlineplus.gov/diabetesmellitus.html" id="45">Diabetes '
        "Mellitus</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/bloodglucose.html" id="6122" '
        'language="Spanish">Glucosa en la sangre</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D001786">Blood Glucose</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="https://www.niddk.nih.gov">National Institute of '
        "Diabetes and Digestive and Kidney Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/a1c.html" '
        'id="6308">A1C</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/carbohydrates.html" '
        'id="3670">Carbohydrates</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetes.html" '
        'id="4">Diabetes</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetesinchildrenandteens.html" '
        'id="6026">Diabetes in Children and Teens</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabetesmedicines.html" '
        'id="4935">Diabetes Medicines</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/diabeticdiet.html" '
        'id="3048">Diabetic Diet</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hyperglycemia.html" '
        'id="6125">Hyperglycemia</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hypoglycemia.html" '
        'id="1264">Hypoglycemia</related-topic>\n'
        "          <see-reference>Blood Sugar</see-reference>\n"
        "          <see-reference>Continuous Glucose Monitoring</see-reference>\n"
        "          <see-reference>Glucose</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/coronaryarterydisease.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Coronary artery disease (CAD) is the most common type '
        "of heart disease. It can lead to angina and heart attack. Read about symptoms and "
        'tests." title="Coronary Artery Disease" '
        'url="https://medlineplus.gov/coronaryarterydisease.html" id="1276" language="English" '
        'date-created="04/04/2000">\n'
        "          <also-called>CAD</also-called>\n"
        "          <also-called>Coronary arteriosclerosis</also-called>\n"
        "          <also-called>Coronary atherosclerosis</also-called>\n"
        "          <also-called>Coronary heart disease</also-called>\n"
        "          <full-summary>&lt;h3&gt;What is coronary artery disease?&lt;/h3&gt;\n"
        "&lt;p&gt;Coronary artery disease (CAD) is the most common type of &lt;a "
        'href="https://medlineplus.gov/heartdiseases.html"&gt;heart disease&lt;/a&gt; in the '
        "United States and a leading cause of death for both men and women.&lt;/p&gt;\n"
        "&lt;p&gt;CAD affects the coronary arteries, which are the blood vessels that carry "
        "blood and oxygen to your heart muscle. When these arteries are damaged or diseased, "
        "your heart does not get the blood it needs.&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/olderadults.html" id="6">Older '
        "Adults</group>\n"
        '          <group url="https://medlineplus.gov/bloodheartandcirculation.html" '
        'id="7">Blood, Heart and Circulation</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/coronaryarterydisease.html" id="1837" '
        'language="Spanish">Enfermedad de las arterias coronarias</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D003324">Coronary Artery Disease</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.nhlbi.nih.gov/">National Heart, Lung, and '
        "Blood Institute</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/angina.html" '
        'id="142">Angina</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/atherosclerosis.html" '
        'id="5400">Atherosclerosis</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/cardiacrehabilitation.html" '
        'id="5617">Cardiac Rehabilitation</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/coronaryarterybypasssurgery.html" id="202">Coronary '
        "Artery Bypass Surgery</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/heartattack.html" id="5">Heart '
        "Attack</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/heartdiseases.html" '
        'id="277">Heart Diseases</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/hearthealthtests.html" '
        'id="6452">Heart Health Tests</related-topic>\n'
        "          <see-reference>Arteriosclerosis, Coronary</see-reference>\n"
        "          <see-reference>Atherosclerosis, Coronary</see-reference>\n"
        "          <see-reference>CAD</see-reference>\n"
        "          <see-reference>Coronary Arteriosclerosis</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "    </list>\n"
        "</nlmSearchResult>"
    ),
    "https://connect.medlineplus.gov/service?knowledgeResponseType=application%2Fjson&mainSearchCriteria.v.c=ZZZ99&mainSearchCriteria.v.cs=2.16.840.1.113883.6.90": {
        "feed": {
            "base": "https://medlineplus.gov/",
            "lang": "en",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "title": {"type": "text", "_value": "MedlinePlus Connect"},
            "updated": {"_value": "2026-10-08T13:38:13Z"},
            "id": {"_value": ""},
            "author": {
                "name": {"_value": "U.S. National Library of Medicine"},
                "uri": {"_value": "https://www.nlm.nih.gov"},
            },
            "subtitle": {
                "type": "text",
                "_value": "MedlinePlus Connect results for ICD-10-CM ZZZ99",
            },
            "category": [
                {"scheme": "mainSearchCriteria.v.c", "term": "ZZZ99"},
                {"scheme": "mainSearchCriteria.v.cs", "term": "ICD10CM"},
                {"scheme": "mainSearchCriteria.v.dn", "term": ""},
                {"scheme": "informationRecipient", "term": "PAT"},
            ],
            "entry": [],
        }
    },
    "https://wsearch.nlm.nih.gov/ws/query?db=healthTopics&retmax=10&rettype=topic&term=postcovidconditionslongcovid&tool=biomedical-knowledge-lookup": (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<nlmSearchResult>\n"
        "  <term>postcovidconditionslongcovid</term>\n"
        "  <file>viv_9jjr78</file>\n"
        "  <server>pvlb7srch15</server>\n"
        "  <count>3</count>\n"
        "  <retstart>0</retstart>\n"
        "  <retmax>10</retmax>\n"
        '  <list num="3" start="0" per="10">\n'
        '    <document rank="0" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Anyone who had COVID-19 can have ongoing symptoms. '
        "Learn about post-COVID conditions (long COVID), including symptoms, diagnosis, "
        'treatments, and prevention." title="Post-COVID Conditions (Long COVID)" '
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807" '
        'language="English" date-created="09/20/2022">\n'
        "          <also-called>Chronic COVID</also-called>\n"
        "          <also-called>Long-haul COVID</also-called>\n"
        "          <also-called>Long-term effects of COVID</also-called>\n"
        "          <full-summary>&lt;h3&gt;What are post-COVID conditions (long "
        "COVID)?&lt;/h3&gt;\n"
        "&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt; '
        "(coronavirus disease 2019) is an illness caused by a virus. Many people get better "
        "within a few days or weeks after being infected with the virus. But others have "
        "post-COVID conditions. They may:&lt;/p&gt;\n"
        "&lt;ul&gt;\n"
        "&lt;li&gt;Have symptoms that linger for weeks, months, or even years&lt;/li&gt; \n"
        "&lt;li&gt;Seem to recover from COVID-19 but then see their symptoms return&lt;/li&gt;\n"
        "&lt;li&gt;Develop new symptoms or new health conditions within a few months of having "
        "COVID-19&lt;/li&gt;\n"
        "&lt;/ul&gt;\n"
        "\n"
        "&lt;p&gt;There are several other names for post-COVID conditions. It is often called "
        "long COVID. But it can also be called long-haul COVID, long-term effects of COVID, "
        "chronic COVID, post-acute COVID-19, and post-acute sequelae of SARS-CoV-2 "
        "(PASC).&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/postcovidconditionslongcovid.html" id="7808" '
        'language="Spanish">Afecciones posteriores al COVID-19 (COVID-19 '
        "persistente)</language-mapped-topic>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000094024">Post-Acute COVID-19 Syndrome</descriptor>\n'
        "          </mesh-heading>\n"
        "          <mesh-heading>\n"
        '            <descriptor id="D000086382">COVID-19</descriptor>\n'
        '            <qualifier id="Q000150">complications</qualifier>\n'
        "          </mesh-heading>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181">COVID-19 '
        "(Coronavirus Disease 2019)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/covid19testing.html" '
        'id="7627">COVID-19 Testing</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/covid19vaccines.html" '
        'id="7647">COVID-19 Vaccines</related-topic>\n'
        "          <see-reference>Long COVID</see-reference>\n"
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="1" '
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="COVID-19 (coronavirus disease 2019) is a respiratory '
        "disease caused by a virus. It can be very contagious. Learn about symptoms, "
        'prevention, and treatment." title="COVID-19 (Coronavirus Disease 2019)" '
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181" '
        'language="English" date-created="08/18/2020">\n'
        "          <also-called>COVID-19</also-called>\n"
        "          <also-called>Coronavirus</also-called>\n"
        "          <full-summary>&lt;p&gt;COVID-19 (coronavirus disease 2019) is an illness "
        "caused by a virus. This virus is a coronavirus called SARS-CoV-2. It spreads when a "
        "person who has the infection breathes out droplets and very small particles that "
        "contain the virus. On this page, you'll find links to resources on important issues "
        "such as symptoms, risks, and how you can protect yourself and your family.&lt;/p&gt;\n"
        "\n"
        "&lt;p&gt;We also have pages on:&lt;/p&gt;\n"
        "&lt;ul&gt; \n"
        '&lt;li&gt;&lt;a href="https://medlineplus.gov/covid19testing.html"&gt;COVID-19 '
        "testing&lt;/a&gt;&lt;/li&gt;\n"
        '&lt;li&gt;&lt;a href="https://medlineplus.gov/covid19vaccines.html"&gt;COVID-19 '
        "vaccines&lt;/a&gt;&lt;/li&gt;\n"
        '&lt;li&gt;&lt;a href="postcovidconditionslongcovid.html" tid="7807"&gt;Post-COVID '
        "conditions (long COVID)&lt;/a&gt;&lt;/li&gt;\n"
        "&lt;/ul&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/lungsandbreathing.html" id="15">Lungs '
        "and Breathing</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/covid19coronavirusdisease2019.html" id="3182" '
        'language="Spanish">Enfermedad del coronavirus 2019 (COVID-19)</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D000086382">COVID-19</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.niaid.nih.gov/">National Institute of '
        "Allergy and Infectious Diseases</primary-institute>\n"
        "          <related-topic "
        'url="https://medlineplus.gov/cleaningdisinfectingandsanitizing.html" '
        'id="7607">Cleaning, Disinfecting, and Sanitizing</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/covid19testing.html" '
        'id="7627">COVID-19 Testing</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/covid19vaccines.html" '
        'id="7647">COVID-19 Vaccines</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/germsandhygiene.html" '
        'id="4182">Germs and Hygiene</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/pneumonia.html" '
        'id="363">Pneumonia</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807">Post-COVID '
        "Conditions (Long COVID)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/travelershealth.html" '
        'id="444">Traveler\'s Health</related-topic>\n'
        '          <related-topic url="https://medlineplus.gov/viralinfections.html" '
        'id="454">Viral Infections</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        '    <document rank="2" url="https://medlineplus.gov/covid19vaccines.html">\n'
        '      <content name="healthTopic">\n'
        '        <health-topic meta-desc="Learn about the vaccines that have been approved and '
        'the vaccination program." title="COVID-19 Vaccines" '
        'url="https://medlineplus.gov/covid19vaccines.html" id="7647" language="English" '
        'date-created="11/09/2020">\n'
        "          <full-summary>&lt;p&gt;&lt;a "
        'href="https://medlineplus.gov/covid19coronavirusdisease2019.html"&gt;COVID-19&lt;/a&gt;  '
        "(coronavirus disease 2019) is an illness caused by a virus. This virus is a "
        "coronavirus called SARS-CoV-2. Most people with COVID-19 have mild symptoms, but\u202f"
        "some people become very sick. You can protect yourself by getting a COVID-19 vaccine. "
        "The vaccines might help keep you from getting sick from COVID-19. And if you do get "
        "sick, the vaccines can reduce your risk for:&lt;/p&gt;&lt;p&gt;&lt;/p&gt;&lt;ul&gt;\n"
        "  &lt;li&gt;Needing to go to urgent care or the emergency room&lt;/li&gt;\n"
        "  &lt;li&gt;Getting severe illness &lt;/li&gt;\n"
        "  &lt;li&gt;Being hospitalized &lt;/li&gt;\n"
        "  &lt;li&gt;Dying&lt;/li&gt;\n"
        "  &lt;li&gt;Getting &lt;a "
        'href="https://medlineplus.gov/postcovidconditionslongcovid.html"&gt;long '
        "COVID&lt;/a&gt; &lt;/li&gt;&lt;/ul&gt;&lt;p&gt;&lt;/p&gt;</full-summary>\n"
        '          <group url="https://medlineplus.gov/infections.html" '
        'id="12">Infections</group>\n'
        '          <group url="https://medlineplus.gov/immunesystem.html" id="22">Immune '
        "System</group>\n"
        "          <language-mapped-topic "
        'url="https://medlineplus.gov/spanish/covid19vaccines.html" id="7648" '
        'language="Spanish">Vacunas contra el COVID-19</language-mapped-topic>\n'
        "          <mesh-heading>\n"
        '            <descriptor id="D000086663">COVID-19 Vaccines</descriptor>\n'
        "          </mesh-heading>\n"
        '          <primary-institute url="http://www.niaid.nih.gov/">National Institute of '
        "Allergy and Infectious Diseases</primary-institute>\n"
        '          <related-topic url="https://medlineplus.gov/childhoodvaccines.html" '
        'id="1342">Childhood Vaccines</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/covid19coronavirusdisease2019.html" id="3181">COVID-19 '
        "(Coronavirus Disease 2019)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/covid19testing.html" '
        'id="7627">COVID-19 Testing</related-topic>\n'
        "          <related-topic "
        'url="https://medlineplus.gov/postcovidconditionslongcovid.html" id="7807">Post-COVID '
        "Conditions (Long COVID)</related-topic>\n"
        '          <related-topic url="https://medlineplus.gov/vaccines.html" '
        'id="294">Vaccines</related-topic>\n'
        "          </health-topic>\n"
        "      </content>\n"
        "    </document>\n"
        "  </list>\n"
        "</nlmSearchResult>"
    ),
}
