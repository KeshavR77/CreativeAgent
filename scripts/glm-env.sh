# GLM reasoning lane via z.ai's Anthropic-compatible endpoint.
# Everything else (search, image gen/source, Conceptial) stays mock/disabled — no other keys needed.
#
# Usage (must be SOURCED so the vars land in your current shell — this app has no load_dotenv):
#   export ZAI_API_KEY="your-z.ai-key"
#   source scripts/glm-env.sh
# then run anything in the same shell: `make dev-backend`, the e2e script, pytest, etc.

export ANTHROPIC_API_KEY="${ZAI_API_KEY:?set ZAI_API_KEY first: export ZAI_API_KEY=your-key}"
export ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic"   # ChatAnthropic reads this from os.environ
export CLAUDE_MODEL="glm-5.2"       # generator (flagship)
export CRITIC_MODEL="glm-4.7"       # MUST differ from CLAUDE_MODEL (critic-independence check); cheaper, distinct
export IDEATOR_FALLBACK="glm"       # labels the ideator brain "glm" truthfully

echo "GLM lane armed: generator=$CLAUDE_MODEL critic=$CRITIC_MODEL base=$ANTHROPIC_BASE_URL"
