import { Navigate, Route, Routes } from 'react-router-dom';
import { DealDiscoveryPage } from './pages/DealDiscoveryPage';
import { HomePage } from './pages/HomePage';
import { MealPlanningPage } from './pages/MealPlanningPage';
import { MealPlansPage } from './pages/MealPlansPage';
import { MealPlanShoppingListPage } from './pages/MealPlanShoppingListPage';
import { ShoppingListPage } from './pages/ShoppingListPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/discover" element={<DealDiscoveryPage />} />
      <Route path="/plan" element={<MealPlanningPage />} />
      <Route path="/meal-plans" element={<MealPlansPage />} />
      <Route path="/meal-plans/:mealPlanId/shopping-list" element={<MealPlanShoppingListPage />} />
      <Route path="/shopping-list/:taskId" element={<ShoppingListPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;