import { Navigate, Route, Routes } from 'react-router-dom';
import { RequireAuth } from './components/RequireAuth';
import { DealDiscoveryPage } from './pages/DealDiscoveryPage';
import { HomePage } from './pages/HomePage';
import { MealPlanningPage } from './pages/MealPlanningPage';
import { MealPlansPage } from './pages/MealPlansPage';
import { MealPlanRecipesPage } from './pages/MealPlanRecipesPage';
import { MealPlanShoppingListPage } from './pages/MealPlanShoppingListPage';
import { ShoppingListPage } from './pages/ShoppingListPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/discover" element={<RequireAuth><DealDiscoveryPage /></RequireAuth>} />
      <Route path="/plan" element={<RequireAuth><MealPlanningPage /></RequireAuth>} />
      <Route path="/meal-plans" element={<RequireAuth><MealPlansPage /></RequireAuth>} />
      <Route path="/recipes/:recipeId" element={<RequireAuth><MealPlanRecipesPage /></RequireAuth>} />
      <Route path="/meal-plans/:mealPlanId/shopping-list" element={<RequireAuth><MealPlanShoppingListPage /></RequireAuth>} />
      <Route path="/shopping-list/:taskId" element={<RequireAuth><ShoppingListPage /></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;