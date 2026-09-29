from evaluator import groq_client, EVAL_MODEL

r = groq_client.chat.completions.create(
    model=EVAL_MODEL,
    messages=[
        {
            "role": "user",
            "content": "Return exactly this JSON: {\"status\":\"TEST_OK\"}"
        }
    ],
    max_tokens=100,
    temperature=0.2
)

print("FULL RESPONSE:")
print(r)

print("\nCONTENT:")
print(repr(r.choices[0].message.content))

print("\nREASONING:")
print(repr(r.choices[0].message.reasoning))