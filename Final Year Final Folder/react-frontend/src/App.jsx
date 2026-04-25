import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Admin from "./pages/Admin";
import PrivateRoute from "./components/PrivateRoute";

const App = () => (
  <Router>
    <Routes>
      <Route path="/auth" element={<Auth />} />
      <Route
        path="/dashboard"
        element={(
          <PrivateRoute>
            <Dashboard />
          </PrivateRoute>
        )}
      />
      <Route
        path="/admin"
        element={(
          <PrivateRoute>
            <Admin />
          </PrivateRoute>
        )}
      />
      <Route path="*" element={<Auth />} />
    </Routes>
  </Router>
);

export default App;
