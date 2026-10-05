$ContainerName = "mealshopper-postgres" 
$DbName = "mealshopper_shopper"
$User = "postgres"
$InDir = ".\infra\postgres\data"
$ContainerTmp = "/tmp/seed_data.sql"

Write-Host "Copying seed data into container..."
docker cp "$InDir\seed_data.sql" "${ContainerName}:${ContainerTmp}"

Write-Host "Executing SQL seed file..."
# Using -f to execute the file that now resides inside the container
docker exec -i $ContainerName psql -U $User -d $DbName -f $ContainerTmp

Write-Host "Cleaning up container temp file..."
docker exec -i $ContainerName rm $ContainerTmp

Write-Host "Import complete."