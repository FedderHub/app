import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import Dashboard from "./pages/Dashboard";
import CreateJobPage from "./pages/CreateJobPage";
import JobDetailPage from "./pages/JobDetailPage";
import PrivateRoute from "./components/PrivateRoute";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes */}
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <Dashboard />
            </PrivateRoute>
          }
        />
        <Route
          path="/jobs/new"
          element={
            <PrivateRoute>
              <CreateJobPage />
            </PrivateRoute>
          }
        />
        {/* Phase 3: job detail page with round metrics */}
        <Route
          path="/jobs/:jobId"
          element={
            <PrivateRoute>
              <JobDetailPage />
            </PrivateRoute>
          }
        />

        {/* Default redirect */}
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
