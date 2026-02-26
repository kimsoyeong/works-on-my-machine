// API Response Types
export interface StepStatus {
  step: string;
  status: 'pending' | 'in_progress' | 'completed' | 'error';
  message?: string;
}

export interface VulnerabilityItem {
  id: string;
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  category: string;
  affected_resource: string;
  title: string;
  description: string;
  evidence: string;
  remediation: string;
  benchmark_ref?: string;
}

export interface AttackScenarioItem {
  id: string;
  name: string;
  mitre_technique: string;
  target_vulnerabilities: string[];
  severity: 'Critical' | 'High' | 'Medium' | 'Low';
  prerequisites: string;
  attack_chain: string[];
  expected_impact: string;
  detection_difficulty: string;
  likelihood: string;
}

export interface PolicyResult {
  status: 'passed' | 'failed';
  violations: Array<{
    rule: string;
    severity: string;
    message: string;
    recommendation: string;
  }>;
  recommendations: Array<{
    rule: string;
    severity: string;
    message: string;
    recommendation: string;
  }>;
  summary: string;
}

export interface SecurityResult {
  final_report: string;
  vulnerability_summary: number;
  severity_counts: Record<string, number>;
  verification_checklist: string[];
}

export interface AnalyzeResponse {
  status: 'success' | 'error';
  task_id: string;
  steps: StepStatus[];
  security?: SecurityResult;
  error?: string;
}

