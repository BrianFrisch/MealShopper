#!/usr/bin/env bash
set -euo pipefail

# ANSI color codes
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
MAGENTA='\033[0;35m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

GATEWAY_URL="http://localhost:5247"

echo -e "${CYAN}=========================================${NC}"
echo -e "${CYAN} 1. Requesting Token via API Gateway     ${NC}"
echo -e "${CYAN}=========================================${NC}"

token_payload=$(cat <<'EOF'
{
  "grant_type": "password",
  "email": "admin@mealshopper.local",
  "password": "AdminP@ssword123!"
}
EOF
)

token_response=$(curl -s -S -w "\n%{http_code}" \
  -X POST "${GATEWAY_URL}/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d "${token_payload}" || true)

http_code=$(echo "${token_response}" | tail -n1)
token_body=$(echo "${token_response}" | sed '$d')

if [ "${http_code}" -ne 200 ]; then
  echo -e "${RED}[ERROR] Failed to obtain token from Gateway (HTTP ${http_code}): ${token_body}${NC}"
  exit 1
fi

access_token=$(echo "${token_body}" | jq -r '.access_token // empty')
expires_in=$(echo "${token_body}" | jq -r '.expires_in // empty')

if [ -z "${access_token}" ]; then
  echo -e "${RED}[ERROR] No access_token found in response: ${token_body}${NC}"
  exit 1
fi

echo -e "${GREEN}[SUCCESS] Acquired Bearer Token!${NC}"
echo -e "${GRAY}Expires in: ${expires_in} seconds${NC}"

# Common Auth Headers (including spoof test headers)
AUTH_HEADERS=(
  -H "Authorization: Bearer ${access_token}"
  -H "X-User-Id: spoofed-hacker-id"
  -H "X-User-Roles: SuperAdmin"
)

echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN} 2. Submitting Meal Plan via API Gateway ${NC}"
echo -e "${CYAN}=========================================${NC}"

intake_payload=$(cat <<'EOF'
{
  "cuisines": ["Mexican", "American"],
  "avoidIngredients": ["peanuts"],
  "address": {
    "street": "123 Hawthorne Blvd",
    "city": "Lawndale",
    "state": "CA",
    "zipCode": "90260"
  },
  "searchRadiusMiles": 10,
  "maxStores": 3
}
EOF
)

intake_headers_file=$(mktemp)
intake_body_file=$(mktemp)
trap 'rm -f "${intake_headers_file}" "${intake_body_file}"' EXIT

#Invoke-RestMethod -Method POST -Uri "$GatewayUrl/v1/admin/stores/import" `
#   -Headers @{ Authorization = "Bearer $Token" } `
#   -ContentType "application/json" `
#   -Body '{"chain_id": "ralphs", "region": "CA"}'

# curl -s -S -w "%{http_code}" -X POST "${GATEWAY_URL}/v1/admin/stores/import" "${AUTH_HEADERS[@]}" -H "Content-Type: application/json" -d '{"chain_id": "ralphs", "region": "CA"}'

intake_status=$(curl -s -S -w "%{http_code}" \
  -X POST "${GATEWAY_URL}/v1/meal-plans" \
  "${AUTH_HEADERS[@]}" \
  -H "Content-Type: application/json" \
  -d "${intake_payload}" \
  -D "${intake_headers_file}" \
  -o "${intake_body_file}" || true)
echo "${intake_status}"
location_header=$(grep -i '^Location:' "${intake_headers_file}" | awk '{print $2}' | tr -d '\r\n')
intake_content=$(cat "${intake_body_file}")

if [[ "${intake_status}" -lt 200 || "${intake_status}" -ge 300 ]]; then
  echo -e "${RED}[ERROR] Failed submitting request through API Gateway (HTTP ${intake_status}): ${intake_content}${NC}"
  exit 1
fi

echo -e "${GREEN}[SUCCESS] Gateway Accepted Request!${NC}"
echo -e "${YELLOW}Status Code : ${intake_status}${NC}"
echo -e "${YELLOW}Location    : ${location_header}${NC}"

job_id=$(echo "${intake_content}" | jq -r '.jobId // empty')
echo -e "${GRAY}Tracked Job : ${job_id}${NC}"

if [ -z "${job_id}" ]; then
  echo -e "${RED}[ERROR] Could not extract jobId from response: ${intake_content}${NC}"
  exit 1
fi

echo -e "\n${CYAN}=========================================${NC}"
echo -e "${CYAN} 3. Polling Task Status via API Gateway  ${NC}"
echo -e "${CYAN}=========================================${NC}"

poll_url="${GATEWAY_URL}/v1/tasks/${job_id}"
max_attempts=300
attempt=1

while [ "${attempt}" -le "${max_attempts}" ]; do
  task_response=$(curl -s -S -w "\n%{http_code}" \
    -X GET "${poll_url}" \
    "${AUTH_HEADERS[@]}" || true)

  poll_http_code=$(echo "${task_response}" | tail -n1)
  task_json=$(echo "${task_response}" | sed '$d')

  if [ "${poll_http_code}" -ne 200 ]; then
    echo -e "${RED}[ERROR] Polling failed (HTTP ${poll_http_code}): ${task_json}${NC}"
    break
  fi

  status=$(echo "${task_json}" | jq -r '.status // empty')
  stage_description=$(echo "${task_json}" | jq -r '.stageDescription // empty')

  echo -e "${WHITE}Attempt ${attempt} : Status = [${status}] | Stage = '${stage_description}'${NC}"

  if [ "${status}" = "Completed" ]; then
    echo -e "\n${GREEN}[COMPLETE] Meal Plan Successfully Assembled!${NC}"
    echo -e "\n${CYAN}========================================================${NC}"
    echo -e "${CYAN}                MEAL PLAN WORKFLOW RESULT               ${NC}"
    echo -e "${CYAN}========================================================${NC}"

    meal_plan_id=$(echo "${task_json}" | jq -r '.result.mealPlanId // ""')
    total_travel_time=$(echo "${task_json}" | jq -r '.result.totalTravelTimeMinutes // ""')
    estimated_cost=$(echo "${task_json}" | jq -r '.result.estimatedTotalTripCost // ""')

    echo "Plan ID               : ${meal_plan_id}"
    echo "Total Travel Time     : ${total_travel_time} mins"
    echo "Estimated Total Cost  : ${estimated_cost}"

    echo -e "\n${GRAY}--------------------------------------------------------${NC}"
    echo -e "${YELLOW}REQUIRED STORES${NC}"
    echo -e "${GRAY}--------------------------------------------------------${NC}"

    while IFS= read -r store; do
      [ -n "${store}" ] && echo -e "  * ${WHITE}${store}${NC}"
    done < <(echo "${task_json}" | jq -r '.result.requiredStores[]? // empty')

    echo -e "\n${GRAY}--------------------------------------------------------${NC}"
    echo -e "${YELLOW}RECIPES & MEAL DETAILS${NC}"
    echo -e "${GRAY}--------------------------------------------------------${NC}"

    num_recipes=$(echo "${task_json}" | jq '.result.recipes | length')
    for ((i = 0; i < num_recipes; i++)); do
      recipe=$(echo "${task_json}" | jq ".result.recipes[$i]")
      recipe_title=$(echo "${recipe}" | jq -r '.recipeTitle // ""')
      recipe_desc=$(echo "${recipe}" | jq -r '.description // ""')

      meal_index=$((i + 1))
      echo -e "\n${GREEN}[${meal_index}] ${recipe_title}${NC}"
      echo -e "    ${GRAY}Description: ${recipe_desc}${NC}"

      # Promotional / Deal Ingredients
      echo -e "    ${CYAN}Ingredients with Deals:${NC}"
      deal_count=$(echo "${recipe}" | jq '.ingredientsWithDeals | length // 0')
      if [ "${deal_count}" -gt 0 ]; then
        for ((j = 0; j < deal_count; j++)); do
          deal_ing=$(echo "${recipe}" | jq ".ingredientsWithDeals[$j]")
          amt=$(echo "${deal_ing}" | jq -r '.amountDescription // ""')
          name=$(echo "${deal_ing}" | jq -r '.name // ""')
          price_desc=$(echo "${deal_ing}" | jq -r '.dealPriceDescription // empty')
          store_name=$(echo "${deal_ing}" | jq -r '.storeName // empty')

          price_text=""
          [ -n "${price_desc}" ] && price_text=" (${price_desc})"

          store_text=""
          [ -n "${store_name}" ] && store_text=" @ ${store_name}"

          echo -e "      + ${WHITE}${amt} ${name}${price_text}${store_text}${NC}"
        done
      else
        echo -e "      ${GRAY}(None)${NC}"
      fi

      # Pantry Staples
      echo -e "    ${YELLOW}Pantry Ingredients:${NC}"
      pantry_count=$(echo "${recipe}" | jq '.pantryIngredients | length // 0')
      if [ "${pantry_count}" -gt 0 ]; then
        for ((k = 0; k < pantry_count; k++)); do
          pantry_ing=$(echo "${recipe}" | jq ".pantryIngredients[$k]")
          p_amt=$(echo "${pantry_ing}" | jq -r '.amountDescription // ""')
          p_name=$(echo "${pantry_ing}" | jq -r '.name // ""')
          echo -e "      - ${GRAY}${p_amt} ${p_name}${NC}"
        done
      else
        echo -e "      ${GRAY}(None)${NC}"
      fi

      # Preparation Instructions
      echo -e "    ${MAGENTA}Instructions:${NC}"
      inst_count=$(echo "${recipe}" | jq '.instructions | length // 0')
      if [ "${inst_count}" -gt 0 ]; then
        for ((step_idx = 0; step_idx < inst_count; step_idx++)); do
          step_text=$(echo "${recipe}" | jq -r ".instructions[$step_idx]")
          echo -e "      ${GRAY}$((step_idx + 1)).${step_text}${NC}"
        done
      else
        echo -e "      ${GRAY}(No instructions provided)${NC}"
      fi
    done

    break
  fi

  if [ "${status}" = "Failed" ]; then
    error_msg=$(echo "${task_json}" | jq -r '.errorMessage // "Unknown error"')
    echo -e "\n${RED}[FAILED] Task failed with message: ${error_msg}${NC}"
    break
  fi

  sleep 1
  attempt=$((attempt + 1))
done