import { Column, ContainedList, ContainedListItem, Grid, InlineNotification, Link, Tag, Tile } from '@carbon/react';
import { PageSubtitle } from '../components/atoms/PageSubtitle';
import { PageTitle } from '../components/atoms/PageTitle';

const fineTuneGuideUrl =
  'https://platform.openai.com/docs/guides/model-optimization?optimization_videos=techniques#fine-tune-a-model';

export function PretrainingPage() {
  return (
    <section className="page-section">
      <PageTitle>微调</PageTitle>
      <PageSubtitle>围绕业务样本微调模型表现，减少复杂提示词成本。</PageSubtitle>
      <InlineNotification
        className="pretrain-notice"
        kind="info"
        lowContrast
        title="功能规划中"
        subtitle="当前提供流程指引与资源入口，后续接入训练任务与状态监控。"
      />
      <Grid condensed fullWidth>
        <Column sm={4} md={8} lg={8}>
          <Tile className="pretrain-tile">
            <div className="pretrain-tile__header">
              <div>
                <h3>实施步骤</h3>
                <p className="session-panel__helper">按步骤准备数据、创建任务、上线模型。</p>
              </div>
              <Tag type="cool-gray">规划中</Tag>
            </div>
            <ContainedList label="步骤清单" kind="on-page" size="sm" isInset>
              <ContainedListItem>准备 JSONL 训练数据（按对话结构拆分并脱敏）。</ContainedListItem>
              <ContainedListItem>完成数据校验与切分，避免过拟合或样本偏差。</ContainedListItem>
              <ContainedListItem>创建训练任务，配置基础模型与训练参数。</ContainedListItem>
              <ContainedListItem>监控训练状态与指标，必要时回滚或重训。</ContainedListItem>
              <ContainedListItem>发布模型版本，回填到 Prompt 与通话链路。</ContainedListItem>
            </ContainedList>
          </Tile>
        </Column>
        <Column sm={4} md={8} lg={4}>
          <Tile className="pretrain-tile">
            <div className="pretrain-tile__header">
              <div>
                <h3>参考资料</h3>
                <p className="session-panel__helper">了解 OpenAI 的 fine-tune 标准流程。</p>
              </div>
            </div>
            <ContainedList label="官方指南" kind="on-page" size="sm" isInset>
              <ContainedListItem
                action={
                  <Link href={fineTuneGuideUrl} target="_blank" rel="noreferrer">
                    查看文档
                  </Link>
                }
              >
                Fine-tune 指南与优化技巧
              </ContainedListItem>
              <ContainedListItem
                action={
                  <Link href={fineTuneGuideUrl} target="_blank" rel="noreferrer">
                    JSONL 格式
                  </Link>
                }
              >
                训练数据格式与字段说明
              </ContainedListItem>
            </ContainedList>
          </Tile>
        </Column>
      </Grid>
    </section>
  );
}
