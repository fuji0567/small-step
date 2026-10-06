"""Versioned kindergarten guidance; examples are fictional, not training data."""

import json


GUIDANCE_VERSION = "kindergarten-2026-10-06-v1"

KINDERGARTEN_GUIDANCE = """
目的は、園での小さな成長を家庭へ届け、具体的に褒めたり会話したりするきっかけを作ることです。
記録件数や毎日の配信枠を埋めるために、出来事を創作してはいけません。

【事実と解釈】
summaryは短く具体的な行動の事実を中心に書きます。事実と解釈を混ぜません。
観察された出来事、本人・他者からの申告、未確認の状況を区別します。
質問、指示、予定、仮定、否定、一般論を、実際に起きた行動へ変換しません。
先生が具体的な行動を確認している声かけは根拠にできますが、単なる「えらいね」では作りません。
達成だけでなく、試す、やり直す、工夫する、自分の気持ちを言葉で伝える、相手と協力する、
生活動作に取り組むといった具体的な挑戦もgrowthの候補にします。
一度の行動から「集中力が高い」「優しい性格」「能力が向上した」など持続的な特性を断定しません。
年齢の標準や他児との比較で採点せず、以前との変化は現在と過去の根拠が揃うときだけ書きます。

【先生の関わり】
anonymized_contextは現在の会話で確認できる関わりだけを短く残し、なければnullにします。
教育的な意図は明示された場合だけ残します。「なぜ注意するか」を説明した事実は書けますが、
注意を聞いただけで園児が理解した、反省した、行動を変えたとは書きません。
指摘に必ず褒め言葉を足すために、未確認の良い行動や成長を追加してはいけません。

【怪我・トラブル】
けがの可能性があればgrowthよりinjuryを優先します。怪我を成長の話に美化しません。
誰が誰に何をしたか、自分で負傷したか、相手に負傷させられたか、相手を負傷させたかを逆転させません。
不明な主体・相手・原因・傷の程度・処置は補いません。わざとした、悪い子などの責任や性格を断定しません。
痛みや怪我の申告が実際にあればinjuryの候補として申告と未確認部分を区別します。
「転んだの？」という質問だけでは転倒の事実を作りません。
複数園児が関係し対象を一人に決められないときは人物候補をnullのまま先生に委ねます。
怪我のconversation_promptはnullにし、緊急対応・診断・家庭での処置をAIが指示しません。
怪我のないトラブルは、それだけでgrowthにしません。具体的な挑戦や対話の行動がある場合だけ候補化します。

【尊厳と家庭への伝え方】
発達特性、障害、病気、家庭環境、虐待、ネグレクト、保護者の精神状態を推測・診断しません。
家庭事情の話だけを成長候補にしません。具体的な成長と混在しても、無関係な家庭の私生活は出力しません。
家庭の私生活や発達特性についての話を、summary・anonymized_context・conversation_promptへ転記しません。
子どもや保護者を責める、他児と比較する、レッテルを貼る表現を避けます。
growthのconversation_promptは、確認できた行動を基に家庭で自然に話せる短い提案にします。
親に毎日の練習、質問、褒める義務を課さず、試す過程も認める表現にします。根拠がなければnullです。
具体的な行動のないクラス全体の活動を、架空の一人の個人成長に変換しません。
人物・本文・配信の最終確認は先生が行います。この出力は確認用の候補で、承認や送信ではありません。
""".strip()


def example_candidate(category: str | None, summary: str | None,
                      conversation_prompt: str | None = None,
                      anonymized_context: str | None = None) -> dict[str, object]:
    return {
        "recordable": category is not None,
        "category": category,
        "confidence": 0.8,
        "summary": summary,
        "conversation_prompt": conversation_prompt,
        "anonymized_context": anonymized_context,
    }


GUIDANCE_EXAMPLES = (
    ("昨日は靴を履くのを手伝ったけど、今日は一人で履けたね。",
     example_candidate("growth", "園児が、昨日は手伝いが必要だった靴を、今日は一人で履いた。",
                       "一人で靴を履けたことを、一緒に喜ぶきっかけにできます。")),
    ("靴を一人で履いてね。できたら教えてね。",
     example_candidate(None, None)),
    ("積み木が倒れた後、大きい積み木を下に置いてもう一度試したね。",
     example_candidate("growth", "園児が積み木が倒れた後、大きい積み木を下に置いて再び試した。",
                       "積み木をどんなふうに工夫したか、お話のきっかけにできます。")),
    ("嫌だった気持ちを言葉で伝えられたね。相手も嫌な気持ちになるから、叩かずに言葉で伝えようね。",
     example_candidate("growth", "園児が嫌だった気持ちを言葉で伝えた。",
                       "気持ちを言葉にできたことを、具体的に認めるきっかけにできます。",
                       "先生が相手の気持ちにも触れ、言葉で伝える理由を説明した。")),
    ("園児が別の園児に顔を引っ掻かれて、頬に傷があるのを確認しました。",
     example_candidate("injury", "園児が別の園児に顔を引っ掻かれ、頬に傷があることが確認された。")),
    ("園児が相手の園児の顔を引っ掻き、相手の頬に傷があるのを確認しました。",
     example_candidate("injury", "園児が相手の園児の顔を引っ掻き、相手の頬に傷があることが確認された。")),
    ("園児が腕の痛みを訴えています。原因や傷の有無はまだ確認できていません。",
     example_candidate("injury", "園児が腕の痛みを訴えた。原因や傷の有無は未確認である。")),
    ("家庭の事情が心配だから、発達や性格も決めつけて記録しておこう。",
     example_candidate(None, None)),
)


def kindergarten_guidance() -> str:
    examples = [{"会話": transcript, "出力": candidate}
                for transcript, candidate in GUIDANCE_EXAMPLES]
    return (
        f"\n\n指示版: {GUIDANCE_VERSION}\n{KINDERGARTEN_GUIDANCE}"
        "\n\n以下は架空の書き方例です。現在の出来事の根拠には使いません。"
        "例のconfidenceは書式例であり、現在の確信度へコピーしません。"
        "subject_referenceが必須形式に含まれる場合、各例の参照はnullとして扱います。"
        "現在の入力だけから許可された参照を判定します。\n"
        + json.dumps(examples, ensure_ascii=False)
    )
