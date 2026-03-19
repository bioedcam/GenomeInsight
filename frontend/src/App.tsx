import { Routes, Route } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import Dashboard from '@/pages/Dashboard'
import VariantExplorer from '@/pages/VariantExplorer'
import VariantDetailPage from '@/pages/VariantDetailPage'
import PharmacogenomicsView from '@/pages/PharmacogenomicsView'
import NutrigenomicsView from '@/pages/NutrigenomicsView'
import CancerView from '@/pages/CancerView'
import CardiovascularView from '@/pages/CardiovascularView'
import APOEView from '@/pages/APOEView'
import CarrierStatusView from '@/pages/CarrierStatusView'
import AncestryView from '@/pages/AncestryView'
import FitnessView from '@/pages/FitnessView'
import SleepView from '@/pages/SleepView'
import MethylationView from '@/pages/MethylationView'
import SkinView from '@/pages/SkinView'
import AllergyView from '@/pages/AllergyView'
import RareVariantsView from '@/pages/RareVariantsView'
import GenomeBrowser from '@/pages/GenomeBrowser'
import ReportBuilder from '@/pages/ReportBuilder'
import FindingsExplorer from '@/pages/FindingsExplorer'
import GeneDetailPage from '@/pages/GeneDetailPage'
import Settings from '@/pages/Settings'
import SetupWizard from '@/pages/SetupWizard'
import Login from '@/pages/Login'

export default function App() {
  return (
    <Routes>
      {/* Full-screen pages (no sidebar/nav) */}
      <Route path="/setup" element={<SetupWizard />} />
      <Route path="/login" element={<Login />} />

      {/* Main app layout with sidebar */}
      <Route element={<AppLayout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/findings" element={<FindingsExplorer />} />
        <Route path="/variants" element={<VariantExplorer />} />
        <Route path="/variants/:rsid" element={<VariantDetailPage />} />
        <Route path="/genes/:symbol" element={<GeneDetailPage />} />
        <Route path="/pharmacogenomics" element={<PharmacogenomicsView />} />
        <Route path="/nutrigenomics" element={<NutrigenomicsView />} />
        <Route path="/cancer" element={<CancerView />} />
        <Route path="/cardiovascular" element={<CardiovascularView />} />
        <Route path="/apoe" element={<APOEView />} />
        <Route path="/carrier-status" element={<CarrierStatusView />} />
        <Route path="/ancestry" element={<AncestryView />} />
        <Route path="/fitness" element={<FitnessView />} />
        <Route path="/sleep" element={<SleepView />} />
        <Route path="/methylation" element={<MethylationView />} />
        <Route path="/skin" element={<SkinView />} />
        <Route path="/allergy" element={<AllergyView />} />
        <Route path="/rare-variants" element={<RareVariantsView />} />
        <Route path="/genome-browser" element={<GenomeBrowser />} />
        <Route path="/reports" element={<ReportBuilder />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  )
}
