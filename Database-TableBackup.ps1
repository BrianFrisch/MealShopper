$ContainerName = "mealshopper-postgres" # Update to match your actual container name
$DbName = "mealshopper_shopper"
$User = "postgres"
$OutDir = ".\infra\postgres\data"
$ContainerTmp = "/tmp/seed_data.sql"

# Ensure the local target directory exists
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Generating SQL dump inside container..."
# Using -f to write directly to the container's file system
docker exec -i $ContainerName pg_dump -U $User -d $DbName -t grocery_chain -t grocery_store --clean --inserts -f $ContainerTmp

Write-Host "Copying dump to local directory..."
docker cp "${ContainerName}:${ContainerTmp}" "$OutDir\seed_data.sql"

Write-Host "Cleaning up container temp file..."
docker exec -i $ContainerName rm $ContainerTmp

Write-Host "Export complete. File saved to $OutDir\seed_data.sql"